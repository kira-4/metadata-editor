"""File scanner to detect new audio files."""
import logging
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
        Process a single audio file.
        
        Args:
            file_path: Path to audio file
        """
        db = SessionLocal()
        try:
            # Check if already processed
            if DatabaseManager.file_already_processed(db, str(file_path)):
                logger.debug(f"File already processed: {file_path}")
                return
            
            logger.info(f"Processing new file: {file_path}")
            
            # Parse filename
            parsed = self.parse_filename(file_path.name)
            if not parsed:
                # Create error entry
                DatabaseManager.create_pending_item(
                    db=db,
                    original_path=str(file_path),
                    current_path=str(file_path),
                    video_title="",
                    channel="",
                    extension=file_path.suffix,
                    error_message="Failed to parse filename format"
                )
                return
            
            video_title, channel = parsed
            
            # Call Gemini to infer metadata
            title, artist, error_msg = gemini_client.infer_metadata(video_title, channel)
            
            if error_msg:
                # Create entry with error
                DatabaseManager.create_pending_item(
                    db=db,
                    original_path=str(file_path),
                    current_path=str(file_path),
                    video_title=video_title,
                    channel=channel,
                    extension=file_path.suffix,
                    error_message=error_msg
                )
                return
            
            # Apply initial metadata (without genre)
            if title and artist:
                success = metadata_processor.apply_metadata(
                    file_path,
                    title=title,
                    artist=artist,
                    genre=None  # Genre set later in UI
                )
                
                if not success:
                    DatabaseManager.create_pending_item(
                        db=db,
                        original_path=str(file_path),
                        current_path=str(file_path),
                        video_title=video_title,
                        channel=channel,
                        extension=file_path.suffix,
                        inferred_title=title,
                        inferred_artist=artist,
                        error_message="Failed to apply metadata"
                    )
                    return
                
                # Rename file
                new_path = metadata_processor.rename_file(file_path, title)
                if not new_path:
                    new_path = file_path
            else:
                new_path = file_path
            
            # Extract artwork if present
            artwork_path = None
            if title:
                artwork_file = config.ARTWORK_DIR / f"{DatabaseManager.file_already_processed.__hash__()}_{file_path.stem}.jpg"
                if metadata_processor.extract_artwork(new_path, artwork_file):
                    artwork_path = str(artwork_file)
            
            # Create pending item in database
            DatabaseManager.create_pending_item(
                db=db,
                original_path=str(file_path),
                current_path=str(new_path),
                video_title=video_title,
                channel=channel,
                extension=file_path.suffix,
                inferred_title=title,
                inferred_artist=artist,
                artwork_path=artwork_path
            )
            
            logger.info(f"Successfully processed: {file_path} -> {new_path}")
            
        except Exception as e:
            logger.error(f"Error processing file {file_path}: {e}", exc_info=True)
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
