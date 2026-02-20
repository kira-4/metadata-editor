"""Library scanner for indexing music files in /music directory."""
import logging
import threading
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime
from mutagen import File as MutagenFile
from mutagen.id3 import ID3NoHeaderError, ID3, TIT2, TPE1, TALB, TPE2, TCON
from mutagen.mp4 import MP4
from mutagen.flac import FLAC
from mutagen.oggvorbis import OggVorbis
from sqlalchemy.orm import Session

from app.config import config
from app.database import get_db, LibraryManager
from app.metadata_processor import metadata_processor

logger = logging.getLogger(__name__)


class LibraryScanner:
    """Scans and indexes music library at /music."""
    
    def __init__(self):
        self.is_scanning = False
        self.scan_thread: Optional[threading.Thread] = None
        self.progress_callback: Optional[Callable] = None
        self.total_files = 0
        self.processed_files = 0
        self.errors = []
        
    def start_scan(self, progress_callback: Optional[Callable] = None, force_full: bool = False):
        """Start a library scan in the background."""
        if self.is_scanning:
            logger.warning("Library scan already in progress")
            return False
        
        self.progress_callback = progress_callback
        self.scan_thread = threading.Thread(target=self._scan_library, args=(force_full,), daemon=True)
        self.scan_thread.start()
        return True
    
    def _scan_library(self, force_full: bool = False):
        """
        Scan library directory and index all audio files.
        
        Args:
            force_full: If True, re-scan all files. If False, only scan new/modified files.
        """
        self.is_scanning = True
        self.total_files = 0
        self.processed_files = 0
        self.errors = []
        
        try:
            logger.info(f"Starting library scan of {config.NAVIDROME_ROOT}")
            
            # Get database session
            db_gen = get_db()
            db: Session = next(db_gen)
            
            try:
                # Find all audio files
                audio_files = []
                for ext in config.AUDIO_EXTENSIONS:
                    audio_files.extend(config.NAVIDROME_ROOT.rglob(f"*{ext}"))
                
                self.total_files = len(audio_files)
                logger.info(f"Found {self.total_files} audio files")
                
                if self.progress_callback:
                    self.progress_callback({
                        'status': 'scanning',
                        'total': self.total_files,
                        'processed': 0,
                        'errors': []
                    })
                
                # Process each file
                for audio_file in audio_files:
                    try:
                        self._index_file(db, audio_file, force_full)
                        self.processed_files += 1
                        
                        # Report progress every 10 files
                        if self.processed_files % 10 == 0 and self.progress_callback:
                            self.progress_callback({
                                'status': 'scanning',
                                'total': self.total_files,
                                'processed': self.processed_files,
                                'errors': self.errors
                            })
                    
                    except Exception as e:
                        error_msg = f"Error processing {audio_file}: {str(e)}"
                        logger.error(error_msg)
                        self.errors.append(error_msg)
                
                # Cleanup: remove tracks for files that no longer exist
                if not force_full:
                    self._cleanup_missing_files(db)
                
                logger.info(f"Library scan complete. Processed {self.processed_files}/{self.total_files} files")
                
                if self.progress_callback:
                    self.progress_callback({
                        'status': 'complete',
                        'total': self.total_files,
                        'processed': self.processed_files,
                        'errors': self.errors
                    })
            
            finally:
                db.close()
        
        except Exception as e:
            logger.error(f"Library scan failed: {e}")
            self.errors.append(f"Scan failed: {str(e)}")
            
            if self.progress_callback:
                self.progress_callback({
                    'status': 'error',
                    'total': self.total_files,
                    'processed': self.processed_files,
                    'errors': self.errors
                })
        
        finally:
            self.is_scanning = False
    
    def _index_file(self, db: Session, file_path: Path, force: bool = False):
        """
        Index a single audio file.
        
        Args:
            db: Database session
            file_path: Path to audio file
            force: If True, re-index even if file hasn't changed
        """
        try:
            # Get file stats
            stat = file_path.stat()
            file_modified = datetime.fromtimestamp(stat.st_mtime)
            file_size = stat.st_size
            
            # Check if file needs indexing
            if not force:
                existing = LibraryManager.get_track_by_path(db, str(file_path))
                if existing and existing.file_modified and existing.file_modified >= file_modified:
                    # File hasn't changed, skip
                    return
            
            # Read metadata (raw tags from file)
            metadata = self._read_raw_metadata(file_path)
            
            # Infer missing metadata (does not modify file yet)
            inferred_metadata = self._infer_missing_metadata(metadata.copy(), file_path)
            
            # Write back to file if changes were made (and ensure required fields exist)
            if self._should_write_metadata(metadata, inferred_metadata):
                logger.info(f"Writing inferred metadata to {file_path}")
                self._write_metadata(file_path, inferred_metadata)
                # Update file modified time in stats since we just modified it
                stat = file_path.stat()
                file_modified = datetime.fromtimestamp(stat.st_mtime)
                file_size = stat.st_size
                # Use the new metadata for the DB
                metadata = inferred_metadata
            else:
                # No write needed, just use the inferred metadata
                metadata = inferred_metadata
            
            # Create or update track
            file_stats = {
                'size': file_size,
                'modified': file_modified
            }
            
            LibraryManager.create_or_update_track(
                db,
                str(file_path),
                metadata,
                file_stats
            )
            
            logger.debug(f"Indexed: {file_path}")
        
        except Exception as e:
            logger.error(f"Failed to index {file_path}: {e}")
            raise
    
    def _read_raw_metadata(self, file_path: Path) -> dict:
        """
        Read raw metadata tags from audio file without inference.
        
        Returns:
            Dictionary with metadata fields found in the file
        """
        try:
            metadata = metadata_processor.read_metadata(file_path)
            if metadata.get("format") == "MP4":
                logger.debug(
                    "Read MP4 atoms from %s: keys=%s, title=%r, artist=%r, album=%r, album_artist=%r, genre=%r, year=%r, track=%r, disc=%r, has_artwork=%r",
                    file_path,
                    metadata.get("tag_keys"),
                    metadata.get("title"),
                    metadata.get("artist"),
                    metadata.get("album"),
                    metadata.get("album_artist"),
                    metadata.get("genre"),
                    metadata.get("year"),
                    metadata.get("track_number"),
                    metadata.get("disc_number"),
                    metadata.get("has_artwork")
                )
            return metadata
        
        except Exception as e:
            logger.error(f"Error reading metadata from {file_path}: {e}")
            return {}

    def _should_write_metadata(self, original: dict, inferred: dict) -> bool:
        """Check if inferred metadata contains important fields missing from original."""
        important_fields = ['title', 'artist', 'album', 'album_artist']
        for field in important_fields:
            # If original is missing the field but inferred has it, we should write
            if not original.get(field) and inferred.get(field):
                return True
        return False

    def _write_metadata(self, file_path: Path, metadata: dict):
        """Write metadata back to file using Mutagen."""
        try:
            audio = MutagenFile(file_path)
            if audio is None:
                return

            modified = False
            
            # Helper to add ID3 tag safely
            def add_id3_tag(key, frame_cls, text_val, encoding=3):
                if text_val:
                    # encoding=3 is utf-8
                    audio.tags.setall(key, [frame_cls(encoding=encoding, text=[str(text_val)])])
                    return True
                return False

            # MP4 / M4A
            if isinstance(audio, MP4):
                mapping = {
                    'title': '\xa9nam',
                    'artist': '\xa9ART',
                    'album': '\xa9alb',
                    'album_artist': 'aART',
                    'genre': '\xa9gen'
                }

                for meta_key, atom_key in mapping.items():
                    value = metadata.get(meta_key)
                    if value and not audio.get(atom_key):
                        audio[atom_key] = [str(value)]
                        modified = True

                if metadata.get("year") and not audio.get('\xa9day'):
                    audio['\xa9day'] = [str(metadata["year"])]
                    modified = True
                if metadata.get("track_number") and not audio.get('trkn'):
                    audio['trkn'] = [(int(metadata["track_number"]), 0)]
                    modified = True
                if metadata.get("disc_number") and not audio.get('disk'):
                    audio['disk'] = [(int(metadata["disc_number"]), 0)]
                    modified = True

            # MP3 (ID3)
            elif hasattr(audio, 'tags') and (isinstance(audio.tags, ID3) or audio.tags is None):
                if audio.tags is None:
                    try:
                        audio.add_tags()
                    except ID3NoHeaderError:
                        pass
                    except Exception:
                        pass # Should have tags now
                
                # Standardize as ID3 if possible, or use the object capabilities
                # If it's an MP3 file, audio.tags is explicitly ID3 usually
                if hasattr(audio.tags, 'add'):
                    if not self._get_tag_text(audio.tags.get('TIT2')) and metadata.get('title'):
                        add_id3_tag('TIT2', TIT2, metadata['title'])
                        modified = True
                    if not self._get_tag_text(audio.tags.get('TPE1')) and metadata.get('artist'):
                        add_id3_tag('TPE1', TPE1, metadata['artist'])
                        modified = True
                    if not self._get_tag_text(audio.tags.get('TALB')) and metadata.get('album'):
                        add_id3_tag('TALB', TALB, metadata['album'])
                        modified = True
                    if not self._get_tag_text(audio.tags.get('TPE2')) and metadata.get('album_artist'):
                        add_id3_tag('TPE2', TPE2, metadata['album_artist'])
                        modified = True
                    if not self._get_tag_text(audio.tags.get('TCON')) and metadata.get('genre'):
                        add_id3_tag('TCON', TCON, metadata['genre'])
                        modified = True
            
            # FLAC / OGG (Vorbis Comments) / Modern formats with Dict-like tags
            elif isinstance(audio, (FLAC, OggVorbis)) and isinstance(audio.tags, dict):
                # For Vorbis/FLAC, keys are case-insensitive usually, but standard is lowercase
                for key, val in [('title', metadata.get('title')), 
                                 ('artist', metadata.get('artist')),
                                 ('album', metadata.get('album')),
                                 ('albumartist', metadata.get('album_artist')),
                                 ('genre', metadata.get('genre'))]:
                    if val and not audio.tags.get(key):
                        audio.tags[key] = str(val)
                        modified = True
            
            if modified:
                audio.save()
                logger.info(f"Updated tags for {file_path}")

        except Exception as e:
            logger.error(f"Failed to write metadata to {file_path}: {e}")

    def _infer_missing_metadata(self, metadata: dict, file_path: Path) -> dict:
        """
        Infer missing metadata from file path.
        
        Rules:
        - Title -> (filename without extension)
        - Album -> (parent directory name)
        - Artist -> (grandparent directory name if applicable)
        """
        # 1. Title fallback
        if not metadata.get('title'):
            metadata['title'] = file_path.stem
            
        # 2. Album fallback
        # Use the parent folder name as album when album metadata is missing.
        if not metadata.get('album'):
            parent_name = file_path.parent.name
            metadata['album'] = parent_name
            
        # 3. Artist fallback
        if not metadata.get('artist'):
            # Try using album_artist if present
            if metadata.get('album_artist'):
                metadata['artist'] = metadata['album_artist']
            else:
                # Try directory structure: /music/Artist/Album/Song
                # We expect Artist to be at /music/Artist
                try:
                    rel_path = file_path.relative_to(config.NAVIDROME_ROOT)
                    if len(rel_path.parts) >= 2:
                        # parts[0] is normally the Artist folder in the standard structure
                        metadata['artist'] = rel_path.parts[0]
                except ValueError:
                    # Not relative to root
                    pass
        
        # 4. Album Artist fallback
        # Always set Album Artist to Artist if missing, to ensure grouping
        if not metadata.get('album_artist') and metadata.get('artist'):
            metadata['album_artist'] = metadata['artist']
        
        return metadata
    
    def _get_tag_text(self, tag) -> Optional[str]:
        """Extract text from ID3 tag."""
        if tag and hasattr(tag, 'text') and len(tag.text) > 0:
            return str(tag.text[0])
        return None
    
    def _get_list_item(self, value) -> Optional[str]:
        """Extract first item from list or return string."""
        if value is None:
            return None
        if isinstance(value, list) and len(value) > 0:
            return str(value[0])
        return str(value) if value else None
    
    def _get_year(self, tag) -> Optional[int]:
        """Extract year from TDRC/TYER tag."""
        if tag and hasattr(tag, 'text') and len(tag.text) > 0:
            text = str(tag.text[0])
            return self._parse_year(text)
        return None
    
    def _parse_year(self, value: Optional[str]) -> Optional[int]:
        """Parse year from string (handles formats like '2024', '2024-01-01')."""
        if not value:
            return None
        try:
            # Extract first 4 digits
            year_str = str(value)[:4]
            year = int(year_str)
            if 1900 <= year <= 2100:
                return year
        except (ValueError, TypeError):
            pass
        return None
    
    def _get_track_number(self, tag) -> Optional[int]:
        """Extract track number from TRCK tag (handles '1' or '1/12' format)."""
        if tag and hasattr(tag, 'text') and len(tag.text) > 0:
            text = str(tag.text[0])
            return self._parse_int(text.split('/')[0])
        return None
    
    def _get_disc_number(self, tag) -> Optional[int]:
        """Extract disc number from TPOS tag."""
        if tag and hasattr(tag, 'text') and len(tag.text) > 0:
            text = str(tag.text[0])
            return self._parse_int(text.split('/')[0])
        return None
    
    def _parse_int(self, value: Optional[str]) -> Optional[int]:
        """Safely parse integer."""
        if not value:
            return None
        try:
            return int(str(value).strip())
        except (ValueError, TypeError):
            return None
    
    def _cleanup_missing_files(self, db: Session):
        """Remove tracks from database for files that no longer exist."""
        from app.database import LibraryTrack
        
        tracks = db.query(LibraryTrack).all()
        removed_count = 0
        
        for track in tracks:
            if not Path(track.file_path).exists():
                LibraryManager.delete_track(db, track.id)
                removed_count += 1
                logger.debug(f"Removed missing file from index: {track.file_path}")
        
        if removed_count > 0:
            logger.info(f"Removed {removed_count} missing files from index")
    
    def get_status(self) -> dict:
        """Get current scan status."""
        return {
            'is_scanning': self.is_scanning,
            'total': self.total_files,
            'processed': self.processed_files,
            'errors': self.errors
        }


# Global scanner instance
library_scanner = LibraryScanner()
