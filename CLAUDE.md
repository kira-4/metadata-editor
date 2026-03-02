# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Run the app locally:**
```bash
python -m uvicorn app.main:app --reload --port 8090
```

**Run tests:**
```bash
python -m pytest tests/ -v          # Full test suite
python -m pytest tests/test_basic.py  # Single test file
```

**Docker:**
```bash
docker-compose up -d
docker-compose logs -f metadata-editor
```

## Architecture

This is a FastAPI + SQLite service that post-processes audio files downloaded by Pinchflat before they reach Navidrome. The core pipeline:

1. **Scanner** (`app/scanner.py`) — background thread polls `/incoming` every 30s, parses filenames (`title###channel.ext`), copies files to `/data/staging/{uuid}/` (originals never modified), then calls Gemini AI to infer Arabic title/artist.
2. **Gemini client** (`app/gemini_client.py`) — uses `gemini-2.0-flash-lite` with Arabic NLP system instructions. Returns title/artist inference; falls back to embedded metadata on failure.
3. **Database** (`app/database.py`) — two SQLAlchemy models: `PendingItem` (files awaiting review) and `LibraryTrack` (indexed /music library). SQLite at `/data/metadata_editor.db`.
4. **Web UI** (`app/static/`) — vanilla JS + CSS, Arabic RTL layout. Connects to SSE endpoint (`/api/events`) for real-time updates. No framework.
5. **Confirm flow** — user reviews/edits in UI, clicks confirm → `api.py` applies final metadata via `metadata_processor.py`, then `mover.py` moves file to `/music/{artist}/{title}/{title}.ext` and cleans up staging.

**Key modules:**
- `app/metadata_processor.py` — multi-format metadata R/W (MP3/ID3, M4A/MP4 atoms, FLAC, OGG). All writes are verified via roundtrip read.
- `app/mover.py` — builds destination path, handles filename collisions (`(1)`, `(2)`, …).
- `app/artist_matching.py` — Arabic-aware fuzzy matching: normalizes Unicode/diacritics/letter variants, then scores with SequenceMatcher + Jaccard. Used by `/api/artists/suggest`.
- `app/library_api.py` — routes for browsing and editing the indexed `/music` library directly.

**Duplicate detection:** SHA256(path + size + mtime) stored as `file_identifier` on `PendingItem`.

## Configuration

Copy `.env.example` to `.env`. Required: `GEMINI_API_KEY`. Key optional vars: `INCOMING_ROOT`, `NAVIDROME_ROOT`, `DATA_DIR`, `SCAN_INTERVAL_SECONDS`, `PORT`.
