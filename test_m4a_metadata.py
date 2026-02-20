"""Integration-style tests for M4A metadata read/write using mutagen."""

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from mutagen.mp4 import MP4

from app.library_scanner import library_scanner
from app.metadata_processor import metadata_processor


class TestM4AMetadata(unittest.TestCase):
    def setUp(self):
        self.ffmpeg = shutil.which("ffmpeg")
        if not self.ffmpeg:
            self.skipTest("ffmpeg not available; skipping M4A integration test")

        self.temp_dir = tempfile.TemporaryDirectory(prefix="test_m4a_")
        self.temp_path = Path(self.temp_dir.name)
        self.source = self.temp_path / "source.m4a"
        self.target = self.temp_path / "target.m4a"

        subprocess.run(
            [
                self.ffmpeg, "-y",
                "-f", "lavfi",
                "-i", "sine=frequency=1000:duration=1",
                "-c:a", "aac",
                "-b:a", "128k",
                str(self.source),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        shutil.copy2(self.source, self.target)

    def tearDown(self):
        if hasattr(self, "temp_dir"):
            self.temp_dir.cleanup()

    def test_m4a_roundtrip_atoms_and_readers(self):
        expected = {
            "title": "عنوان اختبار",
            "artist": "فنان اختبار",
            "album": "عنوان اختبار",
            "album_artist": "فنان اختبار",
            "genre": "لطميات",
            "year": 2026,
            "track_number": 5,
            "disc_number": 1,
        }

        success = metadata_processor.apply_metadata(
            self.target,
            title=expected["title"],
            artist=expected["artist"],
            album=expected["album"],
            genre=expected["genre"],
            year=expected["year"],
            track_number=expected["track_number"],
            disc_number=expected["disc_number"],
        )
        self.assertTrue(success)

        audio = MP4(self.target)
        self.assertEqual(audio.get("\xa9nam"), [expected["title"]])
        self.assertEqual(audio.get("\xa9ART"), [expected["artist"]])
        self.assertEqual(audio.get("aART"), [expected["album_artist"]])
        self.assertEqual(audio.get("\xa9alb"), [expected["album"]])
        self.assertEqual(audio.get("\xa9gen"), [expected["genre"]])
        self.assertEqual(audio.get("\xa9day"), [str(expected["year"])])
        self.assertEqual(audio.get("trkn"), [(expected["track_number"], 0)])
        self.assertEqual(audio.get("disk"), [(expected["disc_number"], 0)])

        processor_read = metadata_processor.read_metadata(self.target)
        scanner_read = library_scanner._read_raw_metadata(self.target)

        for field, value in expected.items():
            self.assertEqual(processor_read.get(field), value, f"processor {field}")
            self.assertEqual(scanner_read.get(field), value, f"scanner {field}")


if __name__ == "__main__":
    unittest.main()
