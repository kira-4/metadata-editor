"""Unit tests for artist normalization and fuzzy matching."""

import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.artist_matching import (
    build_artist_name_key,
    normalize_artist_name,
    rank_artist_candidates,
    score_artist_similarity,
)


class TestArtistMatching(unittest.TestCase):
    def test_normalize_artist_name_handles_arabic_variants(self):
        value = "  مُحَمَّد  بُو  جَبَّارَة  "
        self.assertEqual(normalize_artist_name(value), "محمد بو جباره")

    def test_score_is_high_for_spacing_variant(self):
        query = build_artist_name_key("محمد بو جبارة")
        candidate = build_artist_name_key("محمد بوجبارة")
        self.assertGreaterEqual(score_artist_similarity(query, candidate), 90.0)

    def test_score_is_high_with_extra_words(self):
        query = build_artist_name_key("الحاج محمد بو جبارة الرسمي")
        candidate = build_artist_name_key("محمد بوجبارة")
        self.assertGreaterEqual(score_artist_similarity(query, candidate), 90.0)

    def test_rank_prefers_best_artist_match(self):
        ranked = rank_artist_candidates(
            "محمد بو جبارة",
            [
                {"name": "بسام العبدالله", "track_count": 30},
                {"name": "محمد بوجبارة", "track_count": 4},
                {"name": "محمد الحجيرات", "track_count": 8},
            ],
            limit=5,
        )
        self.assertEqual(ranked[0]["name"], "محمد بوجبارة")
        self.assertGreaterEqual(ranked[0]["score"], 90.0)

    def test_rank_is_low_for_unrelated_names(self):
        ranked = rank_artist_candidates(
            "فنان جديد بالكامل",
            [
                {"name": "محمد بوجبارة", "track_count": 10},
                {"name": "بسام العبدالله", "track_count": 20},
            ],
            limit=5,
        )
        self.assertTrue(all(row["score"] < 72.0 for row in ranked))


if __name__ == "__main__":
    unittest.main()
