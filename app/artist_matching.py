"""Artist name normalization and fuzzy matching helpers."""
from __future__ import annotations

from dataclasses import dataclass
from difflib import SequenceMatcher
import re
import unicodedata
from typing import Dict, Iterable, List, Sequence

# Arabic combining marks / diacritics.
_ARABIC_DIACRITICS_RE = re.compile(r"[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]")
_WHITESPACE_RE = re.compile(r"\s+")

_ARABIC_TRANSLATION_BASE = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
    }
)

_ARABIC_TRANSLATION_WITH_TA_MARBUTA = str.maketrans(
    {
        **{
            k: v
            for k, v in {
                "أ": "ا",
                "إ": "ا",
                "آ": "ا",
                "ٱ": "ا",
                "ى": "ي",
                "ؤ": "و",
                "ئ": "ي",
            }.items()
        },
        "ة": "ه",
    }
)


@dataclass(frozen=True)
class ArtistNameKey:
    """Normalized forms used for matching."""

    original: str
    normalized: str
    tokens: tuple[str, ...]
    unspaced: str


def _normalize_punctuation_to_space(text: str) -> str:
    """Keep letters/numbers, convert punctuation/symbols to spaces."""
    normalized_chars: List[str] = []
    for char in text:
        if char.isspace():
            normalized_chars.append(" ")
            continue

        category = unicodedata.category(char)
        if category and category[0] in {"L", "N"}:
            normalized_chars.append(char)
        else:
            normalized_chars.append(" ")

    return "".join(normalized_chars)


def normalize_artist_name(value: str, *, collapse_ta_marbuta: bool = True) -> str:
    """
    Normalize artist names for fuzzy matching.

    Rules:
    - Unicode normalize (NFKC)
    - lowercase
    - remove Arabic diacritics and tatweel
    - normalize Arabic letter variants
    - normalize punctuation to spaces
    - collapse repeated whitespace
    """
    if not value:
        return ""

    text = unicodedata.normalize("NFKC", value).strip().lower()
    text = text.replace("ـ", "")  # Tatweel
    text = _ARABIC_DIACRITICS_RE.sub("", text)

    translation_table = (
        _ARABIC_TRANSLATION_WITH_TA_MARBUTA if collapse_ta_marbuta else _ARABIC_TRANSLATION_BASE
    )
    text = text.translate(translation_table)

    text = _normalize_punctuation_to_space(text)
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def build_artist_name_key(value: str) -> ArtistNameKey:
    """Build normalized matching forms from the original artist string."""
    original = (value or "").strip()
    normalized = normalize_artist_name(original)
    tokens = tuple(token for token in normalized.split(" ") if token)
    unspaced = "".join(tokens)
    return ArtistNameKey(
        original=original,
        normalized=normalized,
        tokens=tokens,
        unspaced=unspaced,
    )


def _sequence_score(left: str, right: str) -> float:
    if not left or not right:
        return 0.0
    if left == right:
        return 100.0
    return SequenceMatcher(None, left, right).ratio() * 100.0


def _token_stats(query_tokens: Sequence[str], candidate_tokens: Sequence[str]) -> Dict[str, float]:
    if not query_tokens or not candidate_tokens:
        return {
            "jaccard": 0.0,
            "query_coverage": 0.0,
            "candidate_coverage": 0.0,
        }

    query_set = set(query_tokens)
    candidate_set = set(candidate_tokens)
    if not query_set or not candidate_set:
        return {
            "jaccard": 0.0,
            "query_coverage": 0.0,
            "candidate_coverage": 0.0,
        }

    intersection = len(query_set.intersection(candidate_set))
    union = len(query_set.union(candidate_set))

    if intersection == 0:
        return {
            "jaccard": 0.0,
            "query_coverage": 0.0,
            "candidate_coverage": 0.0,
        }

    return {
        "jaccard": intersection / union,
        "query_coverage": intersection / len(query_set),
        "candidate_coverage": intersection / len(candidate_set),
    }


def score_artist_similarity(query: ArtistNameKey, candidate: ArtistNameKey) -> float:
    """Return a 0..100 similarity score between query and candidate."""
    if not query.normalized or not candidate.normalized:
        return 0.0

    if query.normalized == candidate.normalized:
        return 100.0

    spaced_score = _sequence_score(query.normalized, candidate.normalized)
    unspaced_score = _sequence_score(query.unspaced, candidate.unspaced)

    stats = _token_stats(query.tokens, candidate.tokens)
    token_jaccard = stats["jaccard"] * 100.0
    token_coverage = max(stats["query_coverage"], stats["candidate_coverage"]) * 100.0

    base_score = max(
        (0.62 * unspaced_score) + (0.38 * spaced_score),
        (0.55 * token_coverage) + (0.45 * token_jaccard),
        (0.70 * unspaced_score) + (0.30 * token_coverage),
    )

    # Strong containment boost for extra words before/after/in-between.
    if query.unspaced and candidate.unspaced:
        if query.unspaced in candidate.unspaced or candidate.unspaced in query.unspaced:
            if min(len(query.unspaced), len(candidate.unspaced)) >= 3:
                base_score = max(base_score, 92.0)

    if query.unspaced == candidate.unspaced:
        base_score = max(base_score, 97.0)

    return round(min(100.0, max(0.0, base_score)), 2)


def rank_artist_candidates(
    query: str,
    candidates: Iterable[Dict[str, object]],
    *,
    limit: int = 10,
) -> List[Dict[str, object]]:
    """
    Rank candidate artists by fuzzy similarity.

    candidates items are expected as:
    {"name": <artist name>, "track_count": <int optional>}
    """
    query_key = build_artist_name_key(query)
    if not query_key.original:
        return []

    ranked: List[Dict[str, object]] = []
    seen_names = set()

    for candidate in candidates:
        name = str(candidate.get("name") or "").strip()
        if not name or name in seen_names:
            continue

        seen_names.add(name)
        candidate_key = build_artist_name_key(name)
        if not candidate_key.normalized:
            continue

        score = score_artist_similarity(query_key, candidate_key)
        ranked.append(
            {
                "name": name,
                "score": score,
                "track_count": int(candidate.get("track_count") or 0),
                "normalized_name": candidate_key.normalized,
            }
        )

    ranked.sort(
        key=lambda row: (
            row["score"],
            row["track_count"],
            -len(str(row["name"])),
            str(row["name"]),
        ),
        reverse=True,
    )

    return ranked[: max(1, limit)]
