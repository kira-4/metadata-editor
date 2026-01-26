"""Audio metadata processing with mutagen."""
import re
import logging
from pathlib import Path
from typing import Optional, Tuple
import shutil

from mutagen import File as MutagenFile
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TCON, APIC
from mutagen.mp4 import MP4, MP4Cover
from mutagen.flac import FLAC, Picture
from mutagen.oggvorbis import OggVorbis

from app.config import config

logger = logging.getLogger(__name__)


class MetadataProcessor:
    """Handles audio metadata operations."""
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """
        Sanitize filename for filesystem while preserving Arabic characters.
        
        Args:
            filename: The filename to sanitize
            
        Returns:
            Sanitized filename
        """
        # Remove or replace illegal filesystem characters
        # Keep: alphanumeric, Arabic, spaces, hyphens, underscores, periods
        # Replace: / \ : * ? " < > |
        illegal_chars = r'[<>:"/\\|?*]'
        sanitized = re.sub(illegal_chars, '', filename)
        
        # Remove leading/trailing spaces and dots
        sanitized = sanitized.strip('. ')
        
        # If empty after sanitization, use a default
        if not sanitized:
            sanitized = "untitled"
        
        return sanitized
    
    @staticmethod
    def extract_artwork(audio_path: Path, output_path: Path) -> bool:
        """
        Extract embedded artwork from audio file.
        
        Args:
            audio_path: Path to audio file
            output_path: Path to save extracted artwork
            
        Returns:
            True if artwork was extracted, False otherwise
        """
        try:
            audio = MutagenFile(audio_path)
            
            if audio is None:
                return False
            
            # Try to extract artwork based on file type
            if isinstance(audio, MP4):
                if 'covr' in audio:
                    cover_data = audio['covr'][0]
                    with open(output_path, 'wb') as f:
                        f.write(cover_data)
                    return True
            
            elif hasattr(audio, 'tags') and audio.tags:
                # ID3 tags (MP3)
                if isinstance(audio.tags, ID3):
                    for tag in audio.tags.values():
                        if isinstance(tag, APIC):
                            with open(output_path, 'wb') as f:
                                f.write(tag.data)
                            return True
                
                # FLAC
                elif isinstance(audio, FLAC) and audio.pictures:
                    with open(output_path, 'wb') as f:
                        f.write(audio.pictures[0].data)
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error extracting artwork from {audio_path}: {e}")
            return False
    
    @staticmethod
    def apply_metadata(
        audio_path: Path,
        title: str,
        artist: str,
        genre: Optional[str] = None,
        album: str = config.ALBUM_NAME
    ) -> bool:
        """
        Apply metadata to audio file.
        
        Args:
            audio_path: Path to audio file
            title: Track title
            artist: Track artist
            genre: Track genre (optional)
            album: Album name (default: "منوعات")
            
        Returns:
            True if successful, False otherwise
        """
        try:
            audio = MutagenFile(audio_path)
            
            if audio is None:
                logger.error(f"Could not open audio file: {audio_path}")
                return False
            
            # Handle different file formats
            if isinstance(audio, MP4):
                # M4A files
                audio['\xa9nam'] = [title]
                audio['\xa9ART'] = [artist]
                audio['\xa9alb'] = [album]
                audio['aART'] = [artist]  # Album artist
                if genre:
                    audio['\xa9gen'] = [genre]
            
            elif hasattr(audio, 'tags'):
                # MP3 with ID3
                if audio.tags is None:
                    audio.add_tags()
                
                if isinstance(audio.tags, ID3):
                    audio.tags.add(TIT2(encoding=3, text=title))
                    audio.tags.add(TPE1(encoding=3, text=artist))
                    audio.tags.add(TALB(encoding=3, text=album))
                    audio.tags.add(TPE2(encoding=3, text=artist))  # Album artist
                    if genre:
                        audio.tags.add(TCON(encoding=3, text=genre))
                
                # FLAC or OGG
                elif isinstance(audio, (FLAC, OggVorbis)):
                    audio['title'] = title
                    audio['artist'] = artist
                    audio['album'] = album
                    audio['albumartist'] = artist
                    if genre:
                        audio['genre'] = genre
            
            audio.save()
            logger.info(f"Applied metadata to {audio_path}")
            return True
            
        except Exception as e:
            logger.error(f"Error applying metadata to {audio_path}: {e}")
            return False
    
    @staticmethod
    def rename_file(old_path: Path, new_title: str) -> Optional[Path]:
        """
        Rename audio file based on new title.
        
        Args:
            old_path: Current file path
            new_title: New title for the file
            
        Returns:
            New path if successful, None otherwise
        """
        try:
            # Sanitize the title for filename
            safe_title = MetadataProcessor.sanitize_filename(new_title)
            
            # Construct new filename
            new_filename = f"{safe_title}{old_path.suffix}"
            new_path = old_path.parent / new_filename
            
            # Handle collision
            counter = 1
            while new_path.exists() and new_path != old_path:
                new_filename = f"{safe_title} ({counter}){old_path.suffix}"
                new_path = old_path.parent / new_filename
                counter += 1
            
            # Rename if different
            if new_path != old_path:
                old_path.rename(new_path)
                logger.info(f"Renamed {old_path.name} -> {new_path.name}")
            
            return new_path
            
        except Exception as e:
            logger.error(f"Error renaming file {old_path}: {e}")
            return None


metadata_processor = MetadataProcessor()
