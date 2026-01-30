"""File mover to Navidrome library."""
import logging
from pathlib import Path
import shutil
from typing import Optional

from app.config import config
from app.metadata_processor import metadata_processor

logger = logging.getLogger(__name__)


class FileMover:
    """Moves files to Navidrome library with proper structure."""
    
    @staticmethod
    def move_to_navidrome(
        source_path: Path,
        artist: str,
        title: str,
        extension: str
    ) -> Optional[Path]:
        """
        Move file to Navidrome library.
        
        Destination structure: {NAVIDROME_ROOT}/{artist}/منوعات/{title}.{ext}
        
        Args:
            source_path: Current path of the file
            artist: Artist name
            title: Track title
            extension: File extension (with dot)
            
        Returns:
            New path if successful, None otherwise
        """
        try:
            # Sanitize artist and title for directory/filename
            safe_artist = metadata_processor.sanitize_filename(artist)
            safe_title = metadata_processor.sanitize_filename(title)
            
            # Construct destination path
            artist_dir = config.NAVIDROME_ROOT / safe_artist
            album_dir = artist_dir / safe_title
            
            # Create directories
            album_dir.mkdir(parents=True, exist_ok=True)
            
            # Construct destination file path
            dest_filename = f"{safe_title}{extension}"
            dest_path = album_dir / dest_filename
            
            # Handle collisions
            counter = 1
            while dest_path.exists():
                dest_filename = f"{safe_title} ({counter}){extension}"
                dest_path = album_dir / dest_filename
                counter += 1
            
            # Move the file
            shutil.move(str(source_path), str(dest_path))
            
            logger.info(f"Moved {source_path} -> {dest_path}")
            return dest_path
            
        except Exception as e:
            logger.error(f"Error moving file {source_path} to Navidrome: {e}")
            return None


file_mover = FileMover()
