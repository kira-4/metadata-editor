"""Audio metadata processing with mutagen."""
import os
import re
import logging
from pathlib import Path
from typing import Optional, Tuple, Any
import shutil

from mutagen import File as MutagenFile
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TCON, APIC, TDRC, TRCK, TPOS
from mutagen.mp4 import MP4, MP4Cover
from mutagen.flac import FLAC, Picture
from mutagen.oggvorbis import OggVorbis

from app.config import config

logger = logging.getLogger(__name__)


class MetadataProcessor:
    """Handles audio metadata operations."""

    MP4_ATOM_KEYS = ['\xa9nam', '\xa9ART', 'aART', '\xa9alb', '\xa9gen', 'gnre', '\xa9day', 'trkn', 'disk', 'covr']
    
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
    def _first_value(value: Any) -> Optional[str]:
        """Return first string value from mutagen list-like tag value."""
        if value is None:
            return None
        if isinstance(value, (list, tuple)):
            if not value:
                return None
            return str(value[0])
        return str(value)

    @staticmethod
    def _id3_text(tag: Any) -> Optional[str]:
        """Extract text from ID3 frame."""
        if tag is None or not hasattr(tag, "text") or not tag.text:
            return None
        return str(tag.text[0])

    @staticmethod
    def _parse_int(value: Optional[str]) -> Optional[int]:
        """Parse integer from text."""
        if value is None:
            return None
        try:
            return int(str(value).strip())
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _parse_year(value: Optional[str]) -> Optional[int]:
        """Parse year from date-like values (YYYY or YYYY-MM-DD)."""
        if not value:
            return None
        try:
            return int(str(value).strip()[:4])
        except (TypeError, ValueError):
            return None

    @staticmethod
    def read_metadata(audio_path: Path) -> dict:
        """
        Read normalized metadata from an audio file.

        Returns:
            Dictionary with normalized keys used by UI and APIs.
        """
        metadata = {
            "title": None,
            "artist": None,
            "album": None,
            "album_artist": None,
            "genre": None,
            "year": None,
            "track_number": None,
            "disc_number": None,
            "duration": None,
            "has_artwork": False,
            "format": None,
            "tag_keys": []
        }

        try:
            audio = MutagenFile(audio_path)
            if audio is None:
                logger.error(f"Could not open audio file: {audio_path}")
                return metadata

            metadata["format"] = type(audio).__name__

            # MP4 / M4A
            if isinstance(audio, MP4):
                metadata["tag_keys"] = sorted(audio.keys())
                metadata["title"] = MetadataProcessor._first_value(audio.get('\xa9nam'))
                metadata["artist"] = MetadataProcessor._first_value(audio.get('\xa9ART'))
                metadata["album"] = MetadataProcessor._first_value(audio.get('\xa9alb'))
                metadata["album_artist"] = MetadataProcessor._first_value(audio.get('aART'))
                metadata["genre"] = MetadataProcessor._first_value(audio.get('\xa9gen') or audio.get('gnre'))
                metadata["year"] = MetadataProcessor._parse_year(
                    MetadataProcessor._first_value(audio.get('\xa9day'))
                )

                trkn = audio.get('trkn')
                if trkn and len(trkn) > 0 and len(trkn[0]) > 0:
                    metadata["track_number"] = MetadataProcessor._parse_int(trkn[0][0])

                disk = audio.get('disk')
                if disk and len(disk) > 0 and len(disk[0]) > 0:
                    metadata["disc_number"] = MetadataProcessor._parse_int(disk[0][0])

                metadata["has_artwork"] = 'covr' in audio and bool(audio.get('covr'))

            # MP3 / ID3
            elif hasattr(audio, 'tags') and isinstance(audio.tags, ID3):
                metadata["tag_keys"] = sorted(audio.tags.keys())
                metadata["title"] = MetadataProcessor._id3_text(audio.tags.get('TIT2'))
                metadata["artist"] = MetadataProcessor._id3_text(audio.tags.get('TPE1'))
                metadata["album"] = MetadataProcessor._id3_text(audio.tags.get('TALB'))
                metadata["album_artist"] = MetadataProcessor._id3_text(audio.tags.get('TPE2'))
                metadata["genre"] = MetadataProcessor._id3_text(audio.tags.get('TCON'))
                metadata["year"] = MetadataProcessor._parse_year(
                    MetadataProcessor._id3_text(audio.tags.get('TDRC') or audio.tags.get('TYER'))
                )

                track_text = MetadataProcessor._id3_text(audio.tags.get('TRCK'))
                if track_text:
                    metadata["track_number"] = MetadataProcessor._parse_int(track_text.split('/')[0])

                disc_text = MetadataProcessor._id3_text(audio.tags.get('TPOS'))
                if disc_text:
                    metadata["disc_number"] = MetadataProcessor._parse_int(disc_text.split('/')[0])

                metadata["has_artwork"] = any(key.startswith('APIC') for key in audio.tags.keys())

            # FLAC / OGG (Vorbis comments)
            elif isinstance(audio, (FLAC, OggVorbis)):
                tags = audio.tags or {}
                metadata["tag_keys"] = sorted(tags.keys())
                metadata["title"] = MetadataProcessor._first_value(tags.get('title'))
                metadata["artist"] = MetadataProcessor._first_value(tags.get('artist'))
                metadata["album"] = MetadataProcessor._first_value(tags.get('album'))
                metadata["album_artist"] = MetadataProcessor._first_value(tags.get('albumartist'))
                metadata["genre"] = MetadataProcessor._first_value(tags.get('genre'))
                metadata["year"] = MetadataProcessor._parse_year(
                    MetadataProcessor._first_value(tags.get('date'))
                )
                metadata["track_number"] = MetadataProcessor._parse_int(
                    MetadataProcessor._first_value(tags.get('tracknumber'))
                )
                metadata["disc_number"] = MetadataProcessor._parse_int(
                    MetadataProcessor._first_value(tags.get('discnumber'))
                )

                if isinstance(audio, FLAC):
                    metadata["has_artwork"] = len(audio.pictures) > 0

            elif hasattr(audio, 'tags') and isinstance(audio.tags, dict):
                tags = audio.tags or {}
                metadata["tag_keys"] = sorted(tags.keys())

            if hasattr(audio, "info") and hasattr(audio.info, "length"):
                metadata["duration"] = int(audio.info.length)

            return metadata

        except Exception as e:
            logger.error(f"Error reading metadata from {audio_path}: {e}")
            return metadata

    @staticmethod
    def _verify_written_metadata(audio_path: Path, expected: dict) -> bool:
        """Re-read metadata and ensure written fields match expected values."""
        actual = MetadataProcessor.read_metadata(audio_path)
        mismatches = []

        for key, expected_value in expected.items():
            if expected_value is None:
                continue

            actual_value = actual.get(key)

            if key in {"year", "track_number", "disc_number"}:
                if MetadataProcessor._parse_int(actual_value) != MetadataProcessor._parse_int(expected_value):
                    mismatches.append((key, expected_value, actual_value))
            else:
                if str(actual_value or "").strip() != str(expected_value).strip():
                    mismatches.append((key, expected_value, actual_value))

        if mismatches:
            mismatch_text = ", ".join(
                [f"{key}: expected={exp!r}, actual={act!r}" for key, exp, act in mismatches]
            )
            logger.error(f"Metadata verification failed for {audio_path}: {mismatch_text}")
            return False

        return True
    
    @staticmethod
    def apply_metadata(
        audio_path: Path,
        title: str,
        artist: str,
        genre: Optional[str] = None,
        album: str = config.ALBUM_NAME,
        **kwargs
    ) -> bool:
        """
        Apply metadata to audio file.
        
        Args:
            audio_path: Path to audio file
            title: Track title
            artist: Track artist
            genre: Track genre (optional)
            album: Album name (default: "منوعات")
            **kwargs: Additional metadata (year, track_number, disc_number)
            
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
                # Add missing M4A fields
                if kwargs.get('year'):
                    audio['\xa9day'] = [str(kwargs['year'])]
                if kwargs.get('track_number'):
                    track_num = int(kwargs['track_number'])
                    # trkn is (track_num, total_tracks)
                    existing = audio.get('trkn', [(0, 0)])[0]
                    total = existing[1] if len(existing) > 1 else 0
                    audio['trkn'] = [(track_num, total)]
                if kwargs.get('disc_number'):
                    disc_num = int(kwargs['disc_number'])
                    # disk is (disc_num, total_discs)
                    existing = audio.get('disk', [(0, 0)])[0]
                    total = existing[1] if len(existing) > 1 else 0
                    audio['disk'] = [(disc_num, total)]
            
            elif hasattr(audio, 'tags'):
                # MP3 with ID3
                if audio.tags is None:
                    audio.add_tags()
                
                if isinstance(audio.tags, ID3):
                    audio.tags.setall('TIT2', [TIT2(encoding=3, text=title)])
                    audio.tags.setall('TPE1', [TPE1(encoding=3, text=artist)])
                    audio.tags.setall('TALB', [TALB(encoding=3, text=album)])
                    audio.tags.setall('TPE2', [TPE2(encoding=3, text=artist)])  # Album artist
                    if genre:
                        audio.tags.setall('TCON', [TCON(encoding=3, text=genre)])
                    # Add missing ID3 fields
                    if kwargs.get('year'):
                        audio.tags.setall('TDRC', [TDRC(encoding=3, text=str(kwargs['year']))])
                    if kwargs.get('track_number'):
                        audio.tags.setall('TRCK', [TRCK(encoding=3, text=str(kwargs['track_number']))])
                    if kwargs.get('disc_number'):
                        audio.tags.setall('TPOS', [TPOS(encoding=3, text=str(kwargs['disc_number']))])
                
                # FLAC or OGG
                elif isinstance(audio, (FLAC, OggVorbis)):
                    audio['title'] = title
                    audio['artist'] = artist
                    audio['album'] = album
                    audio['albumartist'] = artist
                    if genre:
                        audio['genre'] = genre
                    if kwargs.get('year'):
                        audio['date'] = str(kwargs['year'])
                    if kwargs.get('track_number'):
                        audio['tracknumber'] = str(kwargs['track_number'])
                    if kwargs.get('disc_number'):
                        audio['discnumber'] = str(kwargs['disc_number'])
            
            audio.save()
            expected = {
                "title": title,
                "artist": artist,
                "album": album,
                "album_artist": artist,
                "genre": genre,
                "year": kwargs.get("year"),
                "track_number": kwargs.get("track_number"),
                "disc_number": kwargs.get("disc_number")
            }
            verified = MetadataProcessor._verify_written_metadata(audio_path, expected)
            if not verified:
                return False

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
            os.close(temp_fd)
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
                            audio.tags.setall('TIT2', [TIT2(encoding=3, text=title)])
                        if artist is not None:
                            audio.tags.setall('TPE1', [TPE1(encoding=3, text=artist)])
                        if album is not None:
                            audio.tags.setall('TALB', [TALB(encoding=3, text=album)])
                        if album_artist is not None:
                            audio.tags.setall('TPE2', [TPE2(encoding=3, text=album_artist)])
                        if genre is not None:
                            audio.tags.setall('TCON', [TCON(encoding=3, text=genre)])
                        if year is not None:
                            audio.tags.setall('TDRC', [TDRC(encoding=3, text=str(year))])
                        if track_number is not None:
                            audio.tags.setall('TRCK', [TRCK(encoding=3, text=str(track_number))])
                        if disc_number is not None:
                            audio.tags.setall('TPOS', [TPOS(encoding=3, text=str(disc_number))])
                    
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

                expected = {
                    "title": title,
                    "artist": artist,
                    "album": album,
                    "album_artist": album_artist,
                    "genre": genre,
                    "year": year,
                    "track_number": track_number,
                    "disc_number": disc_number
                }
                verified = MetadataProcessor._verify_written_metadata(audio_path, expected)
                if not verified:
                    return False

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
            os.close(temp_fd)
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

                verification = MetadataProcessor.read_metadata(audio_path)
                if not verification.get("has_artwork"):
                    logger.error(f"Artwork verification failed for {audio_path}")
                    return False

                logger.info(f"Embedded artwork in {audio_path}")
                return True
            
            finally:
                if temp_path.exists():
                    temp_path.unlink()
        
        except Exception as e:
            logger.error(f"Error embedding artwork in {audio_path}: {e}")
            return False


metadata_processor = MetadataProcessor()
