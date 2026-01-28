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
    
    @staticmethod
    def update_metadata_safe(
        audio_path: Path,
        title: Optional[str] = None,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        album_artist: Optional[str] = None,
        genre: Optional[str] = None,
        year: Optional[int] = None,
        track_number: Optional[int] = None,
        disc_number: Optional[int] = None
    ) -> bool:
        """
        Update specific metadata fields atomically (temp file + rename).
        
        Args:
            audio_path: Path to audio file
            Various optional metadata fields to update
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import tempfile
            
            # Create temp file in same directory
            temp_fd, temp_path = tempfile.mkstemp(
                suffix=audio_path.suffix,
                dir=audio_path.parent
            )
            temp_path = Path(temp_path)
            
            try:
                # Copy original to temp
                shutil.copy2(audio_path, temp_path)
                
                # Update metadata on temp file
                audio = MutagenFile(temp_path)
                if audio is None:
                    return False
                
                # Handle different file formats
                if isinstance(audio, MP4):
                    if title is not None:
                        audio['©nam'] = [title]
                    if artist is not None:
                        audio['©ART'] = [artist]
                    if album is not None:
                        audio['©alb'] = [album]
                    if album_artist is not None:
                        audio['aART'] = [album_artist]
                    if genre is not None:
                        audio['©gen'] = [genre]
                    if year is not None:
                        audio['©day'] = [str(year)]
                    if track_number is not None:
                        # M4A track number is tuple (track, total)
                        existing = audio.get('trkn', [(0, 0)])[0]
                        audio['trkn'] = [(track_number, existing[1] if len(existing) > 1 else 0)]
                    if disc_number is not None:
                        existing = audio.get('disk', [(0, 0)])[0]
                        audio['disk'] = [(disc_number, existing[1] if len(existing) > 1 else 0)]
                
                elif hasattr(audio, 'tags'):
                    if audio.tags is None:
                        audio.add_tags()
                    
                    if isinstance(audio.tags, ID3):
                        if title is not None:
                            audio.tags.add(TIT2(encoding=3, text=title))
                        if artist is not None:
                            audio.tags.add(TPE1(encoding=3, text=artist))
                        if album is not None:
                            audio.tags.add(TALB(encoding=3, text=album))
                        if album_artist is not None:
                            audio.tags.add(TPE2(encoding=3, text=album_artist))
                        if genre is not None:
                            audio.tags.add(TCON(encoding=3, text=genre))
                        if year is not None:
                            from mutagen.id3 import TDRC
                            audio.tags.add(TDRC(encoding=3, text=str(year)))
                        if track_number is not None:
                            from mutagen.id3 import TRCK
                            audio.tags.add(TRCK(encoding=3, text=str(track_number)))
                        if disc_number is not None:
                            from mutagen.id3 import TPOS
                            audio.tags.add(TPOS(encoding=3, text=str(disc_number)))
                    
                    elif isinstance(audio, (FLAC, OggVorbis)):
                        if title is not None:
                            audio['title'] = title
                        if artist is not None:
                            audio['artist'] = artist
                        if album is not None:
                            audio['album'] = album
                        if album_artist is not None:
                            audio['albumartist'] = album_artist
                        if genre is not None:
                            audio['genre'] = genre
                        if year is not None:
                            audio['date'] = str(year)
                        if track_number is not None:
                            audio['tracknumber'] = str(track_number)
                        if disc_number is not None:
                            audio['discnumber'] = str(disc_number)
                
                audio.save()
                
                # Atomic replace
                shutil.move(str(temp_path), str(audio_path))
                logger.info(f"Updated metadata for {audio_path}")
                return True
            
            finally:
                # Cleanup temp file if it still exists
                if temp_path.exists():
                    temp_path.unlink()
                    
        except Exception as e:
            logger.error(f"Error updating metadata for {audio_path}: {e}")
            return False
    
    @staticmethod
    def embed_artwork_safe(audio_path: Path, image_data: bytes, mime_type: str) -> bool:
        """
        Embed cover art into audio file atomically.
        
        Args:
            audio_path: Path to audio file
            image_data: Image file bytes
            mime_type: MIME type (e.g., 'image/jpeg', 'image/png')
            
        Returns:
            True if successful, False otherwise
        """
        try:
            import tempfile
            
            # Create temp file
            temp_fd, temp_path = tempfile.mkstemp(
                suffix=audio_path.suffix,
                dir=audio_path.parent
            )
            temp_path = Path(temp_path)
            
            try:
                # Copy original to temp
                shutil.copy2(audio_path, temp_path)
                
                # Embed artwork
                audio = MutagenFile(temp_path)
                if audio is None:
                    return False
                
                if isinstance(audio, MP4):
                    # M4A format
                    if mime_type == 'image/png':
                        cover_format = MP4Cover.FORMAT_PNG
                    else:
                        cover_format = MP4Cover.FORMAT_JPEG
                    
                    audio['covr'] = [MP4Cover(image_data, imageformat=cover_format)]
                
                elif hasattr(audio, 'tags'):
                    if audio.tags is None:
                        audio.add_tags()
                    
                    if isinstance(audio.tags, ID3):
                        # MP3
                        audio.tags.add(
                            APIC(
                                encoding=3,
                                mime=mime_type,
                                type=3,  # Cover (front)
                                desc='Cover',
                                data=image_data
                            )
                        )
                    
                    elif isinstance(audio, FLAC):
                        # FLAC
                        picture = Picture()
                        picture.data = image_data
                        picture.type = 3  # Cover (front)
                        picture.mime = mime_type
                        audio.add_picture(picture)
                
                audio.save()
                
                # Atomic replace
                shutil.move(str(temp_path), str(audio_path))
                logger.info(f"Embedded artwork in {audio_path}")
                return True
            
            finally:
                if temp_path.exists():
                    temp_path.unlink()
        
        except Exception as e:
            logger.error(f"Error embedding artwork in {audio_path}: {e}")
            return False


metadata_processor = MetadataProcessor()
