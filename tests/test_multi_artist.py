"""Tests for multi-artist and album_artist support."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from mutagen import File as MutagenFile
from mutagen.mp4 import MP4
from mutagen.id3 import ID3, TPE1, TPE2
from mutagen.flac import FLAC

from app.artist_matching import derive_album_artist
from app.metadata_processor import metadata_processor
from app.mover import FileMover
from app.gemini_client import GeminiClient


class TestGeminiMultiArtistParsing(unittest.TestCase):
    """Test Gemini response parsing for artists and album_artist."""

    def setUp(self):
        self.client = GeminiClient()

    def test_parse_three_line_response(self):
        text = """
title: يا حسين
artists: باسم الكربلائي; حيدر البراك
album_artist: قناة الولاء
"""
        title, artists, album_artist = self.client._parse_response(text)
        self.assertEqual(title, "يا حسين")
        self.assertEqual(artists, "باسم الكربلائي; حيدر البراك")
        self.assertEqual(album_artist, "قناة الولاء")

    def test_parse_legacy_two_line_response(self):
        text = """
title: يا حسين
artist: باسم الكربلائي
"""
        title, artists, album_artist = self.client._parse_response(text)
        self.assertEqual(title, "يا حسين")
        self.assertEqual(artists, "باسم الكربلائي")
        self.assertIsNone(album_artist)

    def test_parse_json_response(self):
        text = '{"title": "يا حسين", "artists": "باسم الكربلائي; حيدر البراك", "album_artist": "قناة الولاء"}'
        title, artists, album_artist = self.client._parse_response(text)
        self.assertEqual(title, "يا حسين")
        self.assertEqual(artists, "باسم الكربلائي; حيدر البراك")
        self.assertEqual(album_artist, "قناة الولاء")


class TestMetadataProcessorMultiArtist(unittest.TestCase):
    """Test metadata processor multi-value artist read/write."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="test_multi_artist_")
        self.temp_path = Path(self.temp_dir.name)

    def tearDown(self):
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def _create_m4a(self, name):
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            self.skipTest("ffmpeg not available")
        path = self.temp_path / name
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1", "-c:a", "aac", "-b:a", "128k", str(path)],
            check=True, capture_output=True, text=True,
        )
        return path

    def _create_mp3(self, name):
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            self.skipTest("ffmpeg not available")
        path = self.temp_path / name
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1", "-c:a", "libmp3lame", "-b:a", "128k", str(path)],
            check=True, capture_output=True, text=True,
        )
        return path

    def _create_flac(self, name):
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            self.skipTest("ffmpeg not available")
        path = self.temp_path / name
        subprocess.run(
            [ffmpeg, "-y", "-f", "lavfi", "-i", "sine=frequency=1000:duration=1", "-c:a", "flac", str(path)],
            check=True, capture_output=True, text=True,
        )
        return path

    def test_m4a_multi_artist_roundtrip(self):
        path = self._create_m4a("multi.m4a")
        success = metadata_processor.apply_metadata(
            path,
            title="يا حسين",
            artist="باسم الكربلائي; حيدر البراك",
            album_artist="قناة الولاء",
            genre="لطميات",
        )
        self.assertTrue(success)

        audio = MP4(path)
        self.assertEqual(audio.get("\xa9ART"), ["باسم الكربلائي", "حيدر البراك"])
        self.assertEqual(audio.get("aART"), ["قناة الولاء"])

        read = metadata_processor.read_metadata(path)
        self.assertEqual(read["artist"], "باسم الكربلائي; حيدر البراك")
        self.assertEqual(read["album_artist"], "قناة الولاء")

    def test_mp3_multi_artist_roundtrip(self):
        path = self._create_mp3("multi.mp3")
        success = metadata_processor.apply_metadata(
            path,
            title="يا حسين",
            artist="باسم الكربلائي; حيدر البراك",
            album_artist="قناة الولاء",
            genre="لطميات",
        )
        self.assertTrue(success)

        audio = MutagenFile(path)
        tpe1 = audio.tags.get("TPE1")
        self.assertIsNotNone(tpe1)
        self.assertEqual(list(tpe1.text), ["باسم الكربلائي", "حيدر البراك"])

        read = metadata_processor.read_metadata(path)
        self.assertEqual(read["artist"], "باسم الكربلائي; حيدر البراك")
        self.assertEqual(read["album_artist"], "قناة الولاء")

    def test_flac_multi_artist_roundtrip(self):
        path = self._create_flac("multi.flac")
        success = metadata_processor.apply_metadata(
            path,
            title="يا حسين",
            artist="باسم الكربلائي; حيدر البراك",
            album_artist="قناة الولاء",
            genre="لطميات",
        )
        self.assertTrue(success)

        read = metadata_processor.read_metadata(path)
        self.assertEqual(read["artist"], "باسم الكربلائي; حيدر البراك")
        self.assertEqual(read["album_artist"], "قناة الولاء")

    def test_update_metadata_safe_multi_artist(self):
        path = self._create_m4a("update.m4a")
        # First apply single artist
        metadata_processor.apply_metadata(path, title="ت", artist="أ", album_artist="أ")
        # Then update to multi
        success = metadata_processor.update_metadata_safe(
            path,
            artist="أ; ب",
            album_artist="قناة الولاء"
        )
        self.assertTrue(success)

        read = metadata_processor.read_metadata(path)
        self.assertEqual(read["artist"], "أ; ب")
        self.assertEqual(read["album_artist"], "قناة الولاء")


class TestMoverAlbumArtist(unittest.TestCase):
    """Test mover uses album_artist for path building."""

    def test_build_destination_path_uses_album_artist(self):
        dest = FileMover.build_destination_path(
            album_artist="قناة الولاء",
            title="يا حسين",
            extension=".m4a"
        )
        self.assertIn("قناة الولاء", str(dest))
        self.assertIn("يا حسين", str(dest))
        self.assertTrue(str(dest).endswith("يا حسين.m4a"))


class TestJoinArtistsHelper(unittest.TestCase):
    """Test MetadataProcessor._join_artists helper."""

    def test_join_list(self):
        result = metadata_processor._join_artists(["A", "B", "C"])
        self.assertEqual(result, "A; B; C")

    def test_join_single(self):
        result = metadata_processor._join_artists("A")
        self.assertEqual(result, "A")

    def test_join_none(self):
        result = metadata_processor._join_artists(None)
        self.assertIsNone(result)

    def test_join_empty_list(self):
        result = metadata_processor._join_artists([])
        self.assertIsNone(result)


class TestDeriveAlbumArtist(unittest.TestCase):
    """Test derive_album_artist helper."""

    def test_prefers_channel_match(self):
        result = derive_album_artist("باسم الكربلائي; حيدر البراك", "قناة باسم الكربلائي")
        self.assertEqual(result, "باسم الكربلائي")

    def test_fallback_to_first_artist(self):
        result = derive_album_artist("باسم الكربلائي; حيدر البراك", "قناة الولاء")
        self.assertEqual(result, "باسم الكربلائي")

    def test_single_artist(self):
        result = derive_album_artist("باسم الكربلائي", "قناة الولاء")
        self.assertEqual(result, "باسم الكربلائي")

    def test_empty_artists_fallback_to_channel(self):
        result = derive_album_artist("", "قناة الولاء")
        self.assertEqual(result, "قناة الولاء")

    def test_channel_contained_in_artist(self):
        result = derive_album_artist("السيد وائل السلامي", "كربلاء لايف")
        # No match, fallback to first artist
        self.assertEqual(result, "السيد وائل السلامي")


if __name__ == "__main__":
    unittest.main()
