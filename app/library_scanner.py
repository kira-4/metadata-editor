"""Library scanner for indexing music files in /music directory."""
import logging
import threading
from pathlib import Path
from typing import Optional, Callable
from datetime import datetime
from mutagen import File as MutagenFile
from sqlalchemy.orm import Session

from app.config import config
from app.database import get_db, LibraryManager

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
            
            # Read metadata
            metadata = self._read_metadata(file_path)
            
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
    
    def _read_metadata(self, file_path: Path) -> dict:
        """
        Read metadata from audio file.
        
        Returns:
            Dictionary with metadata fields
        """
        try:
            audio = MutagenFile(file_path)
            
            if audio is None:
                return {}
            
            metadata = {}
            
            # Handle different file formats
            if hasattr(audio, 'tags') and audio.tags:
                # MP3 (ID3)
                if hasattr(audio.tags, 'get'):
                    metadata['title'] = self._get_tag_text(audio.tags.get('TIT2'))
                    metadata['artist'] = self._get_tag_text(audio.tags.get('TPE1'))
                    metadata['album'] = self._get_tag_text(audio.tags.get('TALB'))
                    metadata['album_artist'] = self._get_tag_text(audio.tags.get('TPE2'))
                    metadata['genre'] = self._get_tag_text(audio.tags.get('TCON'))
                    metadata['year'] = self._get_year(audio.tags.get('TDRC') or audio.tags.get('TYER'))
                    metadata['track_number'] = self._get_track_number(audio.tags.get('TRCK'))
                    metadata['disc_number'] = self._get_disc_number(audio.tags.get('TPOS'))
                    metadata['has_artwork'] = any(tag.startswith('APIC') for tag in audio.tags.keys())
                
                # FLAC / OGG
                elif isinstance(audio.tags, dict):
                    metadata['title'] = self._get_list_item(audio.tags.get('title'))
                    metadata['artist'] = self._get_list_item(audio.tags.get('artist'))
                    metadata['album'] = self._get_list_item(audio.tags.get('album'))
                    metadata['album_artist'] = self._get_list_item(audio.tags.get('albumartist'))
                    metadata['genre'] = self._get_list_item(audio.tags.get('genre'))
                    metadata['year'] = self._parse_year(self._get_list_item(audio.tags.get('date')))
                    metadata['track_number'] = self._parse_int(self._get_list_item(audio.tags.get('tracknumber')))
                    metadata['disc_number'] = self._parse_int(self._get_list_item(audio.tags.get('discnumber')))
                    
                    if hasattr(audio, 'pictures'):
                        metadata['has_artwork'] = len(audio.pictures) > 0
            
            # M4A / MP4
            elif hasattr(audio, 'get'):
                metadata['title'] = self._get_list_item(audio.get('©nam'))
                metadata['artist'] = self._get_list_item(audio.get('©ART'))
                metadata['album'] = self._get_list_item(audio.get('©alb'))
                metadata['album_artist'] = self._get_list_item(audio.get('aART'))
                metadata['genre'] = self._get_list_item(audio.get('©gen'))
                metadata['year'] = self._parse_year(self._get_list_item(audio.get('©day')))
                
                # Track number in M4A is a tuple (track, total)
                trkn = audio.get('trkn')
                if trkn and len(trkn) > 0 and len(trkn[0]) > 0:
                    metadata['track_number'] = int(trkn[0][0])
                
                disk = audio.get('disk')
                if disk and len(disk) > 0 and len(disk[0]) > 0:
                    metadata['disc_number'] = int(disk[0][0])
                
                metadata['has_artwork'] = 'covr' in audio
            
            # Duration (common to all formats)
            if hasattr(audio.info, 'length'):
                metadata['duration'] = int(audio.info.length)
            
            return metadata
        
        except Exception as e:
            logger.error(f"Error reading metadata from {file_path}: {e}")
            return {}
    
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
