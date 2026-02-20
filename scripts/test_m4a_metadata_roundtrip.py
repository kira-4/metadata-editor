#!/usr/bin/env python3
"""Roundtrip verification for M4A metadata write/read paths."""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
import sys

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from mutagen.mp4 import MP4

from app.library_scanner import library_scanner
from app.metadata_processor import metadata_processor


def run_command(cmd):
    """Run a shell command and return stdout."""
    result = subprocess.run(cmd, capture_output=True, text=True, check=True)
    return result.stdout


def assert_equal(actual, expected, label):
    """Simple assertion helper with readable errors."""
    if actual != expected:
        raise AssertionError(f"{label}: expected {expected!r}, got {actual!r}")


def main():
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is required for this test script")

    with tempfile.TemporaryDirectory(prefix="m4a_roundtrip_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        source = tmp_path / "source.m4a"
        target = tmp_path / "target.m4a"

        # Create a valid M4A sample (1-second sine wave).
        run_command([
            ffmpeg, "-y",
            "-f", "lavfi",
            "-i", "sine=frequency=1000:duration=1",
            "-c:a", "aac",
            "-b:a", "128k",
            str(source),
        ])
        shutil.copy2(source, target)

        expected = {
            "title": "عنوان تجريبي",
            "artist": "فنان تجريبي",
            "album": "عنوان تجريبي",
            "album_artist": "فنان تجريبي",
            "genre": "لطميات",
            "year": 2025,
            "track_number": 7,
            "disc_number": 2,
        }

        write_ok = metadata_processor.apply_metadata(
            target,
            title=expected["title"],
            artist=expected["artist"],
            album=expected["album"],
            genre=expected["genre"],
            year=expected["year"],
            track_number=expected["track_number"],
            disc_number=expected["disc_number"],
        )
        assert_equal(write_ok, True, "apply_metadata returned success")

        # Atom-level verification
        mp4_file = MP4(target)
        assert_equal(mp4_file.get("\xa9nam"), [expected["title"]], "MP4 atom ©nam")
        assert_equal(mp4_file.get("\xa9ART"), [expected["artist"]], "MP4 atom ©ART")
        assert_equal(mp4_file.get("aART"), [expected["album_artist"]], "MP4 atom aART")
        assert_equal(mp4_file.get("\xa9alb"), [expected["album"]], "MP4 atom ©alb")
        assert_equal(mp4_file.get("\xa9gen"), [expected["genre"]], "MP4 atom ©gen")
        assert_equal(mp4_file.get("\xa9day"), [str(expected["year"])], "MP4 atom ©day")
        assert_equal(mp4_file.get("trkn"), [(expected["track_number"], 0)], "MP4 atom trkn")
        assert_equal(mp4_file.get("disk"), [(expected["disc_number"], 0)], "MP4 atom disk")

        # Application readback verification
        processor_readback = metadata_processor.read_metadata(target)
        for field, expected_value in expected.items():
            assert_equal(processor_readback.get(field), expected_value, f"metadata_processor.read_metadata({field})")

        scanner_readback = library_scanner._read_raw_metadata(target)
        for field, expected_value in expected.items():
            assert_equal(scanner_readback.get(field), expected_value, f"library_scanner._read_raw_metadata({field})")

        # Final probe output for troubleshooting
        try:
            ffprobe = shutil.which("ffprobe")
            if ffprobe:
                ffprobe_output = run_command([
                    ffprobe,
                    "-v", "error",
                    "-show_entries", "format_tags",
                    "-of", "json",
                    str(target),
                ])
                print("ffprobe format tags:")
                print(ffprobe_output.strip())
        except Exception:
            pass

        print("M4A metadata roundtrip test passed.")
        print(json.dumps(scanner_readback, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
