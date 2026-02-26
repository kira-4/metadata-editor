"""Unit tests for scanner Gemini integration behavior."""

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.scanner import FileScanner


class TestScannerGeminiIntegration(unittest.TestCase):
    def setUp(self):
        self.scanner = FileScanner()

    @patch("app.scanner.gemini_client.infer_metadata")
    def test_prefers_gemini_when_available(self, mock_infer):
        mock_infer.return_value = ("AI Title", "AI Artist", None, "raw")

        title, artist, error, raw = self.scanner.infer_metadata_with_fallback(
            video_title="Video",
            channel="Channel",
            existing_title="Embedded Title",
            existing_artist="Embedded Artist",
        )

        self.assertEqual(title, "AI Title")
        self.assertEqual(artist, "AI Artist")
        self.assertIsNone(error)
        self.assertEqual(raw, "raw")
        mock_infer.assert_called_once_with("Video", "Channel")

    @patch("app.scanner.gemini_client.infer_metadata")
    def test_uses_embedded_fallback_for_missing_gemini_fields(self, mock_infer):
        mock_infer.return_value = (None, "AI Artist", "Failed to parse Gemini response", "raw")

        title, artist, error, raw = self.scanner.infer_metadata_with_fallback(
            video_title="Video",
            channel="Channel",
            existing_title="Embedded Title",
            existing_artist="Embedded Artist",
        )

        self.assertEqual(title, "Embedded Title")
        self.assertEqual(artist, "AI Artist")
        self.assertEqual(error, "Failed to parse Gemini response")
        self.assertEqual(raw, "raw")

    @patch("app.scanner.gemini_client.infer_metadata")
    def test_uses_embedded_metadata_when_gemini_fails(self, mock_infer):
        mock_infer.return_value = (None, None, "Gemini API error: bad key", "")

        title, artist, error, raw = self.scanner.infer_metadata_with_fallback(
            video_title="Video",
            channel="Channel",
            existing_title="Embedded Title",
            existing_artist="Embedded Artist",
        )

        self.assertEqual(title, "Embedded Title")
        self.assertEqual(artist, "Embedded Artist")
        self.assertEqual(error, "Gemini API error: bad key")
        self.assertEqual(raw, "")

    @patch("app.scanner.gemini_client.infer_metadata")
    def test_returns_none_when_no_gemini_or_embedded_metadata(self, mock_infer):
        mock_infer.return_value = (None, None, "Gemini API error", "")

        title, artist, error, raw = self.scanner.infer_metadata_with_fallback(
            video_title="Video",
            channel="Channel",
            existing_title=None,
            existing_artist=None,
        )

        self.assertIsNone(title)
        self.assertIsNone(artist)
        self.assertEqual(error, "Gemini API error")
        self.assertEqual(raw, "")


if __name__ == "__main__":
    unittest.main()
