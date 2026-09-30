"""Find and merge artist spelling variants (e.g. الأكرف / الاكرف, السيد / سيد).

Grouping is exact on a variant key — the normalized name with leading honorifics
removed — rather than a fuzzy score, so different people with similar names
(حاتم العبدالله / بسام العبدالله) are never grouped.

Merging retags every affected track (artist + album artist) and moves files out
of a source artist's folder into the target's, so both Navidrome (tags) and the
folder tree end up with one artist. plan_merge() and apply_merge() share one plan,
so the preview is exactly what gets applied.
"""
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from app.artist_matching import normalize_artist_name
from app.config import config
from app.database import LibraryManager, LibraryTrack
from app.metadata_processor import metadata_processor
from app.mover import FileMover

logger = logging.getLogger(__name__)

# Normalized forms (after أ→ا etc.), with and without the article
_HONORIFICS = {"الشيخ", "شيخ", "السيد", "سيد", "الحاج", "حاج", "الملا", "ملا", "الحافظ", "حافظ"}


def variant_key(name: str) -> str:
    """Normalized, honorific-free, space-free key: equal keys = same artist."""
    tokens = normalize_artist_name(name).split()
    while len(tokens) > 1 and tokens[0] in _HONORIFICS:
        tokens = tokens[1:]
    return "".join(tokens)


def find_variant_groups(db: Session) -> List[dict]:
    """Groups of 2+ artist names sharing a variant key, most-used name first."""
    groups: Dict[str, List[dict]] = {}
    for artist in LibraryManager.get_all_artists(db):
        key = variant_key(artist["name"])
        if key:
            groups.setdefault(key, []).append(
                {"name": artist["name"], "track_count": artist["track_count"]}
            )

    result = []
    for variants in groups.values():
        if len(variants) < 2:
            continue
        variants.sort(key=lambda v: (-v["track_count"], v["name"]))
        result.append({"variants": variants, "suggested": variants[0]["name"]})
    result.sort(key=lambda g: -sum(v["track_count"] for v in g["variants"]))
    return result


def _replace_names(value: Optional[str], sources: set, target: str) -> Optional[str]:
    """Swap source names for target inside a ';'-list, dropping duplicates."""
    if not value:
        return value
    names: List[str] = []
    for name in LibraryManager._split_artists(value):
        name = target if name in sources else name
        if name not in names:
            names.append(name)
    return "; ".join(names)


def _moved_path(file_path: Path, old_album_artist: Optional[str], new_album_artist: str) -> Optional[Path]:
    """New path when the file sits in the old album artist's top-level folder."""
    try:
        relative = file_path.relative_to(config.NAVIDROME_ROOT)
    except ValueError:
        return None
    if len(relative.parts) < 2 or not old_album_artist:
        return None
    if relative.parts[0] != metadata_processor.sanitize_filename(old_album_artist):
        return None
    new_folder = metadata_processor.sanitize_filename(new_album_artist)
    if new_folder == relative.parts[0]:
        return None
    return config.NAVIDROME_ROOT / new_folder / Path(*relative.parts[1:])


def plan_merge(db: Session, sources: List[str], target: str) -> List[dict]:
    """Per-track changes merging `sources` into `target`. Touches nothing."""
    source_set = {s for s in sources if s and s != target}
    if not source_set:
        return []

    candidates = set()
    for name in source_set:
        candidates.update(LibraryManager._filtered_tracks(db, artist=name).all())

    plan = []
    for track in sorted(candidates, key=lambda t: t.id):
        artist_after = _replace_names(track.artist, source_set, target)
        album_artist_after = _replace_names(track.album_artist, source_set, target)
        if artist_after == track.artist and album_artist_after == track.album_artist:
            continue  # substring match only (e.g. a different artist)
        new_path = _moved_path(Path(track.file_path), track.album_artist, album_artist_after or target)
        plan.append({
            "track_id": track.id,
            "title": track.title,
            "file_path": track.file_path,
            "artist_before": track.artist,
            "artist_after": artist_after,
            "album_artist_before": track.album_artist,
            "album_artist_after": album_artist_after,
            "new_path": str(new_path) if new_path else None,
            "blocked": bool(new_path and new_path.exists()),
        })
    return plan


def _remove_empty_dirs(start: Path) -> None:
    """Remove now-empty folders from `start` up to (not including) the library root."""
    root = config.NAVIDROME_ROOT.resolve()
    current = start
    while current.resolve() != root and current.resolve().is_relative_to(root):
        try:
            current.rmdir()  # only succeeds when empty
        except OSError:
            return
        current = current.parent


def apply_merge(db: Session, sources: List[str], target: str) -> dict:
    """Apply plan_merge: verified retag, then move, then reindex. Per-track results."""
    from app.library_scanner import library_scanner

    results = {"successful": 0, "failed": 0, "errors": [], "moved": 0}
    for change in plan_merge(db, sources, target):
        path = Path(change["file_path"])
        try:
            if not path.exists():
                raise RuntimeError("File not found")
            if not metadata_processor.update_metadata_safe(
                path,
                artist=change["artist_after"],
                album_artist=change["album_artist_after"],
            ):
                raise RuntimeError("Failed to write tags")

            final_path = path
            if change["new_path"] and not change["blocked"]:
                final_path = Path(change["new_path"])
                final_path.parent.mkdir(parents=True, exist_ok=True)
                FileMover._atomic_move(path, final_path)
                _remove_empty_dirs(path.parent)
                LibraryManager.delete_track(db, change["track_id"])
                results["moved"] += 1

            library_scanner._index_file(db, final_path, force=True)
            results["successful"] += 1
        except Exception as e:
            logger.error(f"Artist merge failed for {path}: {e}")
            results["failed"] += 1
            results["errors"].append({"file_path": str(path), "error": str(e)})
    return results
