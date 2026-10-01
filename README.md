# محرر الأصوات الولائية

محرر الأصوات الولائية هو خدمة ما بعد المعالجة لتدفق Pinchflat → Navidrome. يقوم تلقائياً بمعالجة الملفات الصوتية التي تم تنزيلها، واستخلاص العنوان/الفنان، ثم يتيح مراجعتها وتعديلها قبل حفظ الوسوم ونقلها إلى مكتبة Navidrome.

A FastAPI + SQLite service that sits between Pinchflat and Navidrome. It picks up new downloads, asks an
LLM (via [OpenRouter](https://openrouter.ai)) for the Arabic title and performers, and holds each file for
review. After you confirm, it writes the tags and moves the file into the library.

## Features

- **Automatic scanning** of the Pinchflat download directory. Originals are copied to staging and never modified.
- **AI metadata** through OpenRouter with ordered fallback models. If inference fails, it falls back to the embedded tags.
- **Review UI** (Arabic, RTL, works on a phone) with live updates over SSE, an artist autocomplete, and genre presets.
- **Safe writes**: tags are verified by reading them back before the file is replaced. The move into `/music` is atomic, so Navidrome never sees a half-written file.
- **Duplicate check**: if the destination already exists, you choose *replace* or *keep both*.
- **Library browser**: edit tags and artwork of indexed tracks, and merge artist spelling variants.
- **Optional Telegram notifications** for items that need attention (configured in the UI).
- Formats: MP3, M4A, FLAC, OGG.

## Quick start (Docker)

Requirements: Docker with Compose, an [OpenRouter API key](https://openrouter.ai/keys), Pinchflat, and Navidrome.

1. **Configure**

   ```bash
   cp .env.example .env
   # set OPENROUTER_API_KEY, and PUID/PGID to the owner of your music library (`ls -ln /path/to/music`)
   ```

2. **Point the volumes** in `docker-compose.yml` at your directories:

   | Host | Container | Purpose |
   |---|---|---|
   | Pinchflat downloads | `/incoming` | Files to process |
   | Navidrome library | `/music` | Destination |
   | `./data` | `/data` | SQLite DB, staging, artwork cache |

   Create the host directories **before** the first start. Otherwise Docker creates them as root, and
   the container (which runs as `PUID:PGID`) can't write to them.

3. **Start**

   ```bash
   docker compose up -d
   docker compose ps          # STATUS should become "healthy"
   ```

4. Open `http://<host>:8090`.

### Upgrading from a root-run container

Older versions ran as root, so `data/` and some library folders are owned by `0:0`. Fix that once:

```bash
docker compose down
sudo chown -R 1000:1000 ./data /path/to/music   # use your PUID:PGID
docker compose up -d
```

## Configuration

| Variable | Default | Description |
|---|---|---|
| `OPENROUTER_API_KEY` | *(required)* | OpenRouter key. Without it, inference fails and items fall back to embedded tags. |
| `OPENROUTER_MODEL` | `deepseek/deepseek-v4-flash` | Primary model id. |
| `OPENROUTER_FALLBACK_MODELS` | *(none)* | Comma-separated backups. OpenRouter tries them in order. |
| `OPENROUTER_BASE_URL` | `https://openrouter.ai/api/v1` | API base URL. |
| `PUID` / `PGID` | `1000` / `1000` | User/group the container runs as. Files in `/music` get this owner. |
| `INCOMING_ROOT` | `/incoming` | Download directory (inside the container). |
| `NAVIDROME_ROOT` | `/music` | Library directory (inside the container). |
| `DATA_DIR` | `/data` | Database, staging and artwork cache. |
| `SCAN_INTERVAL_SECONDS` | `30` | How often `/incoming` is polled. |
| `PORT` | `8090` | Web UI port. |
| `TZ` | `America/Los_Angeles` | Timezone (compose). |
| `APP_NAME` | `محرر الأصوات الولائية` | Title shown in the UI and API docs. |

## How it works

1. **Detect.** Every `SCAN_INTERVAL_SECONDS` the scanner walks `/incoming` for files named
   `{video_title}###{channel}.{ext}` (e.g. `زواج الغالي###ملا حاتم العبدالله.mp3`). Each new file is copied
   to `/data/staging/{uuid}/`. A file is identified by a hash of its path, size and mtime, so it is only
   picked up once.
2. **Infer.** `video_title` and `channel` go to OpenRouter as the user message. The instructions in
   `app/openrouter_client.py` (`SYSTEM_INSTRUCTIONS`) ask for:

   ```
   title: <Arabic title>
   artists: <artist1>; <artist2>
   album_artist: <one of the artists, preferring the channel>
   ```

   Prefixes like `ملا`/`الحاج` are dropped. `السيد` and `الشيخ` are kept.
3. **Review.** The card shows artwork, the editable title/artist, the original source, and genre presets
   (مواليد وأفراح، لطميات، شعر، قرآن، أدعية, or a custom value). It also shows a dry-run of the destination path.
4. **Confirm.** The draft you see is sent with the confirm. Tags are written and verified, then the file
   is moved atomically to:

   ```
   {NAVIDROME_ROOT}/{album_artist}/{title}/{title}.{ext}
   ```

   The track is indexed into the library browser immediately and the staging copy is removed.

Deleting a pending item removes its staging copy and the original in `/incoming`. Completed items can't
be deleted from the queue.

## Development

```bash
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt pytest
export OPENROUTER_API_KEY=... INCOMING_ROOT=./incoming NAVIDROME_ROOT=./music DATA_DIR=./data
python -m uvicorn app.main:app --reload --port 8090
```

Tests use temp directories and never call OpenRouter or Telegram. The audio roundtrip tests need
`ffmpeg` on `PATH` and are skipped without it.

```bash
python -m pytest tests/ -v
```

## API

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/health` | `{status, scanner_running}`; 503 if the database is unusable. Used by the healthcheck. |
| GET | `/api/pending` | Review queue. |
| POST | `/api/pending/{id}/update` | Save a draft (title, artist, genre). |
| GET | `/api/pending/{id}/dry-run` | Destination preview and whether it already exists. |
| POST | `/api/pending/{id}/confirm` | Apply the draft and move. Returns 409 if the destination exists and no `on_conflict` is given. |
| DELETE | `/api/pending/{id}` | Discard an item. |
| GET | `/api/artwork/{id}` | Artwork of a pending item. |
| GET | `/api/artists/suggest` | Arabic-aware artist autocomplete. |
| GET | `/api/events` | SSE stream of queue changes. |
| GET | `/api/library/{artists,albums,genres,tracks,stats}` | Browse the indexed library. |
| POST | `/api/library/tracks/{id}/update`, `/api/library/tracks/batch-update` | Edit library tags. |
| GET/POST | `/api/library/tracks/{id}/artwork` | Read or replace track artwork. |
| GET/POST | `/api/library/artist-variants`, `/api/library/artist-merge` | Find and merge artist spellings. |
| POST/GET | `/api/library/rescan`, `/api/library/rescan/status` | Re-index `/music` (read-only unless `?repair=true`). |
| GET/PUT/POST | `/api/settings/telegram`, `/api/settings/telegram/test` | Telegram notification settings. |

## Troubleshooting

- **Container is `unhealthy`**: run `docker compose logs metadata-editor`. Usually `/data` isn't writable by `PUID:PGID`.
- **Files not detected**: check the `title###channel.ext` naming and the `/incoming` volume path.
- **No AI suggestions**: check `OPENROUTER_API_KEY`, and the model ids against [openrouter.ai/models](https://openrouter.ai/models). The raw model response is kept on the item for debugging.
- **Permission denied writing to `/music`**: `PUID`/`PGID` must match the library owner (see *Upgrading* above).

## License

Provided as-is for personal use.
