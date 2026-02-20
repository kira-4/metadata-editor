"""File scanner to detect new audio files."""
import logging
import hashlib
import shutil
import uuid
from pathlib import Path
from typing import List, Tuple, Optional
import time
import threading

from app.config import config
from app.database import DatabaseManager, SessionLocal
from app.gemini_client import gemini_client
from app.metadata_processor import metadata_processor

logger = logging.getLogger(__name__)


class FileScanner:
    """Scans incoming directory for new audio files."""
    
    def __init__(self):
        """Initialize scanner."""
        self.running = False
        self.thread = None
    
    @staticmethod
    def parse_filename(filename: str) -> Optional[Tuple[str, str]]:
        """
        Parse filename in format: {{video_title}}###{{channel}}.{{ext}}
        
        Args:
            filename: The filename to parse
            
        Returns:
            Tuple of (video_title, channel) or None if parsing fails
        """
        # Remove extension
        name_without_ext = Path(filename).stem
        
        # Split by ###
        if '###' not in name_without_ext:
            logger.warning(f"Filename does not contain '###' separator: {filename}")
            return None
        
        parts = name_without_ext.split('###', 1)
        if len(parts) != 2:
            logger.warning(f"Could not parse filename: {filename}")
            return None
        
        video_title = parts[0].strip()
        channel = parts[1].strip()
        
        if not video_title or not channel:
            logger.warning(f"Empty video_title or channel in: {filename}")
            return None
        
        return video_title, channel
    
    @staticmethod
    def compute_file_identifier(file_path: Path) -> str:
        """
        Compute a stable identifier for a file based on path, size, and mtime.
        This identifier remains stable across renames if the file content is unchanged.
        
        Args:
            file_path: Path to the file
            
        Returns:
            SHA256 hash as hex string
        """
        stat = file_path.stat()
        # Use original path + size + mtime for identification
        # This ensures the same file gets the same identifier even if renamed
        identifier_string = f"{file_path.absolute()}|{stat.st_size}|{stat.st_mtime}"
        return hashlib.sha256(identifier_string.encode()).hexdigest()
    
    def scan_directory(self) -> List[Path]:
        """
        Scan incoming directory for audio files.
        
        Returns:
            List of audio file paths
        """
        audio_files = []
        
        if not config.INCOMING_ROOT.exists():
            logger.warning(f"Incoming directory does not exist: {config.INCOMING_ROOT}")
            return audio_files
        
        # Recursively find audio files
        for ext in config.AUDIO_EXTENSIONS:
            audio_files.extend(config.INCOMING_ROOT.rglob(f"*{ext}"))
        
        return audio_files
    
    def process_file(self, file_path: Path):
        """
        Process a single audio file using staging directory to prevent duplicates.
        
        Args:
            file_path: Path to audio file in /incoming
        """
        db = SessionLocal()
        staged_path = None
        staging_dir = None
        
        try:
            # Compute stable file identifier
            file_identifier = self.compute_file_identifier(file_path)
            
            # Check if already processed by identifier
            existing = DatabaseManager.get_item_by_identifier(db, file_identifier)
            if existing:
                logger.debug(f"File already processed (identifier match): {file_path}")
                return
            
            # Also check by original path (backward compatibility)
            if DatabaseManager.file_already_processed(db, str(file_path)):
                logger.debug(f"File already processed (path match): {file_path}")
                return
            
            logger.info(f"Processing new file: {file_path}")
            
            # Create unique staging directory
            staging_dir = config.STAGING_DIR / str(uuid.uuid4())
            staging_dir.mkdir(parents=True, exist_ok=True)
            
            # Copy file to staging (NEVER modify files in /incoming)
            staged_path = staging_dir / file_path.name
            shutil.copy2(file_path, staged_path)
            logger.info(f"Copied to staging: {file_path} -> {staged_path}")
            
            # Extract artwork from staged file (EARLY EXTRACTION)
            artwork_path = None
            file_hash = hashlib.md5(file_identifier.encode()).hexdigest()[:8]
            artwork_file = config.ARTWORK_DIR / f"{file_hash}_{file_path.stem}.jpg"
            if metadata_processor.extract_artwork(staged_path, artwork_file):
                artwork_path = str(artwork_file)

            # Read existing embedded metadata (important for M4A imports)
            existing_metadata = metadata_processor.read_metadata(staged_path)
            logger.info(
                "Imported existing metadata from %s: format=%s, tag_keys=%s, title=%r, artist=%r, album=%r, genre=%r, year=%r, track=%r, disc=%r",
                staged_path,
                existing_metadata.get("format"),
                existing_metadata.get("tag_keys"),
                existing_metadata.get("title"),
                existing_metadata.get("artist"),
                existing_metadata.get("album"),
                existing_metadata.get("genre"),
                existing_metadata.get("year"),
                existing_metadata.get("track_number"),
                existing_metadata.get("disc_number"),
            )
            
            # Parse filename
            parsed = self.parse_filename(file_path.name)
            if not parsed:
                # Create manual edit entry with fallback values
                inferred_title = existing_metadata.get("title") or file_path.stem
                inferred_artist = existing_metadata.get("artist") or ""
                DatabaseManager.create_pending_item(
                    db=db,
                    original_path=str(file_path),
                    current_path=str(staged_path),
                    video_title=file_path.stem,  # Fallback to stem
                    channel="Unknown",
                    extension=file_path.suffix,
                    inferred_title=inferred_title,
                    inferred_artist=inferred_artist,
                    artwork_path=artwork_path, # Include artwork if found
                    status="needs_manual",
                    error_message="Failed to parse filename - please edit manually",
                    file_identifier=file_identifier
                )
                logger.warning(f"Created manual edit entry for unparsed file: {file_path}")
                return
            
            video_title, channel = parsed

            existing_title = (existing_metadata.get("title") or "").strip()
            existing_artist = (existing_metadata.get("artist") or "").strip()
            # Prefer existing embedded metadata when available
            title = existing_title or None
            artist = existing_artist or None
            error_msg = None
            raw_response = ""

            # Fallback to Gemini if any required field is missing
            if not title or not artist:
                gemini_title, gemini_artist, error_msg, raw_response = gemini_client.infer_metadata(video_title, channel)
                title = title or (gemini_title.strip() if gemini_title else None)
                artist = artist or (gemini_artist.strip() if gemini_artist else None)

            # If still missing data, create needs_manual item
            if not title or not artist:
                DatabaseManager.create_pending_item(
                    db=db,
                    original_path=str(file_path),
                    current_path=str(staged_path),
                    video_title=video_title,
                    channel=channel,
                    extension=file_path.suffix,
                    inferred_title=title or video_title,  # Fallback to video_title
                    inferred_artist=artist or channel,    # Fallback to channel
                    artwork_path=artwork_path,
                    status="needs_manual",
                    error_message=f"Metadata detection failed: {error_msg or 'Incomplete data'}",
                    file_identifier=file_identifier,
                    raw_gemini_response=raw_response
                )
                logger.warning(f"Created needs_manual entry for Gemini failure: {file_path}")
                return
            
            # Apply initial metadata to STAGED file (without genre)
            if title and artist:
                success = metadata_processor.apply_metadata(
                    staged_path,
                    title=title,
                    artist=artist,
                    album=title,
                    genre=existing_metadata.get("genre"),
                    year=existing_metadata.get("year"),
                    track_number=existing_metadata.get("track_number"),
                    disc_number=existing_metadata.get("disc_number"),
                )
                
                if not success:
                    # Create needs_manual entry instead of error
                    DatabaseManager.create_pending_item(
                        db=db,
                        original_path=str(file_path),
                        current_path=str(staged_path),
                        video_title=video_title,
                        channel=channel,
                        extension=file_path.suffix,
                        inferred_title=title,
                        inferred_artist=artist,
                        artwork_path=artwork_path,
                        status="needs_manual",
                        error_message="Failed to apply metadata tags - please check file",
                        file_identifier=file_identifier,
                        raw_gemini_response=raw_response
                    )
                    logger.warning(f"Created manual edit entry for metadata failure: {file_path}")
                    return
            
            # Create pending item in database pointing to STAGED file
            item = DatabaseManager.create_pending_item(
                db=db,
                original_path=str(file_path),
                current_path=str(staged_path),
                video_title=video_title,
                channel=channel,
                extension=file_path.suffix,
                inferred_title=title,
                inferred_artist=artist,
                artwork_path=artwork_path,
                status="pending",
                file_identifier=file_identifier,
                raw_gemini_response=raw_response if title and artist else None
            )
            
            logger.info(f"Successfully processed: {file_path} -> staged (item_id={item.id})")
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}", exc_info=True)
            # Try to create an error entry so the file appears in UI
            try:
                file_identifier = self.compute_file_identifier(file_path)
                DatabaseManager.create_pending_item(
                    db=db,
                    original_path=str(file_path),
                    current_path=str(staged_path) if staged_path else str(file_path),
                    video_title=file_path.stem,
                    channel="Unknown",
                    extension=file_path.suffix,
                    inferred_title=None,
                    inferred_artist=None,
                    status="error",  # Generic system error
                    error_message=f"Processing error: {str(e)}",
                    file_identifier=file_identifier
                )
            except Exception as inner_e:
                logger.error(f"Failed to create error entry: {inner_e}")
            # Clean up staging on error
            if staging_dir and staging_dir.exists():
                try:
                    shutil.rmtree(staging_dir)
                except:
                    pass
        finally:
            db.close()
    
    def scan_loop(self):
        """Main scanning loop."""
        logger.info("Starting file scanner loop")
        
        while self.running:
            try:
                # Scan for files
                files = self.scan_directory()
                logger.debug(f"Found {len(files)} audio files")
                
                # Process each file
                for file_path in files:
                    if not self.running:
                        break
                    self.process_file(file_path)
                
                # Wait before next scan
                time.sleep(config.SCAN_INTERVAL_SECONDS)
                
            except Exception as e:
                logger.error(f"Error in scan loop: {e}", exc_info=True)
                time.sleep(5)  # Wait a bit before retrying
    
    def start(self):
        """Start the scanner in a background thread."""
        if self.running:
            logger.warning("Scanner already running")
            return
        
        self.running = True
        self.thread = threading.Thread(target=self.scan_loop, daemon=True)
        self.thread.start()
        logger.info("File scanner started")
    
    def stop(self):
        """Stop the scanner."""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("File scanner stopped")


# Global scanner instance
file_scanner = FileScanner()
