"""File mover to Navidrome library."""
import errno
import logging
import os
from pathlib import Path
import shutil
from typing import Optional, Dict

from app.config import config
from app.metadata_processor import metadata_processor

logger = logging.getLogger(__name__)


class FileMover:
    """Moves files to Navidrome library with proper structure."""

    @staticmethod
    def build_destination_path(
        album_artist: str,
        title: str,
        extension: str
    ) -> Path:
        """
        Build destination path without moving the file.

        Destination structure: {NAVIDROME_ROOT}/{album_artist}/{title}/{title}.{ext}
        """
        safe_album_artist = metadata_processor.sanitize_filename(album_artist)
        safe_title = metadata_processor.sanitize_filename(title)
        safe_album = safe_title

        artist_dir = config.NAVIDROME_ROOT / safe_album_artist
        album_dir = artist_dir / safe_album
        dest_filename = f"{safe_title}{extension}"
        dest_path = album_dir / dest_filename

        counter = 1
        while dest_path.exists():
            dest_filename = f"{safe_title} ({counter}){extension}"
            dest_path = album_dir / dest_filename
            counter += 1

        return dest_path

    @staticmethod
    def get_destination_preview(
        album_artist: str,
        title: str,
        extension: str
    ) -> Dict[str, object]:
        """Return dry-run preview for move destination and write permissions."""
        destination = FileMover.build_destination_path(album_artist, title, extension)
        closest_existing_parent = destination.parent
        while not closest_existing_parent.exists() and closest_existing_parent != closest_existing_parent.parent:
            closest_existing_parent = closest_existing_parent.parent

        writable = closest_existing_parent.exists() and os.access(closest_existing_parent, os.W_OK)
        root_exists = config.NAVIDROME_ROOT.exists()
        root_writable = root_exists and os.access(config.NAVIDROME_ROOT, os.W_OK)

        return {
            "destination_path": str(destination),
            "destination_dir": str(destination.parent),
            "closest_existing_parent": str(closest_existing_parent),
            "navidrome_root": str(config.NAVIDROME_ROOT),
            "navidrome_root_exists": root_exists,
            "navidrome_root_writable": root_writable,
            "destination_parent_writable": writable
        }
    
    @staticmethod
    def _atomic_move(source_path: Path, dest_path: Path) -> None:
        """
        Move so the final name only ever points at a complete file.

        Same filesystem: a single rename. Across filesystems (staging and /music are
        separate mounts in Docker): copy to a hidden temp name in the destination
        directory, fsync, then rename into place — Navidrome skips dotfiles, so it
        never indexes a half-written track.
        """
        try:
            os.rename(source_path, dest_path)
            return
        except OSError as e:
            if e.errno != errno.EXDEV:
                raise

        temp_path = dest_path.parent / f".{dest_path.name}.partial"
        try:
            shutil.copy2(source_path, temp_path)
            with open(temp_path, "rb") as f:
                os.fsync(f.fileno())
            os.replace(temp_path, dest_path)
        except BaseException:
            temp_path.unlink(missing_ok=True)
            raise
        source_path.unlink()

    @staticmethod
    def move_to_navidrome(
        source_path: Path,
        album_artist: str,
        title: str,
        extension: str
    ) -> Optional[Path]:
        """
        Move file to Navidrome library.
        
        Destination structure: {NAVIDROME_ROOT}/{album_artist}/{title}/{title}.{ext}
        
        Args:
            source_path: Current path of the file
            album_artist: Album artist name (used for folder naming)
            title: Track title
            extension: File extension (with dot)
            
        Returns:
            New path if successful, None otherwise
        """
        try:
            dest_path = FileMover.build_destination_path(album_artist, title, extension)
            dest_path.parent.mkdir(parents=True, exist_ok=True)

            FileMover._atomic_move(source_path, dest_path)

            logger.info(f"Moved {source_path} -> {dest_path}")
            return dest_path
            
        except Exception as e:
            logger.error(f"Error moving file {source_path} to Navidrome: {e}")
            return None


file_mover = FileMover()
