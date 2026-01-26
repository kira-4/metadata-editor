# Audio Metadata Editor

Post-processing service for Pinchflat → Navidrome workflow. Automatically processes downloaded audio files, uses Gemini AI to infer Arabic metadata, provides a modern Web UI for genre selection and editing, then moves files to your Navidrome library with proper tagging.

## Features

- 🔍 **Automatic Scanning**: Watches Pinchflat download directory for new audio files
- 🤖 **AI-Powered Metadata**: Uses Gemini Flash-Lite to infer Arabic titles and artists
- 🎨 **Modern Dark UI**: Clean, responsive interface with Arabic font support
- 🎵 **Multi-Format Support**: Handles MP3, M4A, FLAC, and OGG files
- ✏️ **Inline Editing**: Edit title, artist, and select genre before moving files
- 📦 **Docker Ready**: One-container deployment with volume mounts
- ⚡ **Real-Time Updates**: SSE-powered live UI updates as new files arrive

## Quick Start

### Prerequisites

- Docker and Docker Compose
- Gemini API key ([Get one here](https://aistudio.google.com/app/apikey))
- Pinchflat instance downloading audio files
- Navidrome music library

### Installation

1. **Clone or create the project directory**
   ```bash
   cd /path/to/metadata-editor
   ```

2. **Configure environment variables**
   
   Copy the example file and add your Gemini API key:
   ```bash
   cp .env.example .env
   nano .env  # Add your GEMINI_API_KEY
   ```

3. **Update docker-compose.yml volumes**
   
   Edit `docker-compose.yml` and set the correct paths for:
   - Pinchflat downloads directory → `/incoming`
   - Navidrome music library → `/music`

4. **Start the service**
   ```bash
   docker-compose up -d
   ```

5. **Open the Web UI**
   
   Navigate to: `http://localhost:8090`

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `INCOMING_ROOT` | `/incoming` | Pinchflat download directory (inside container) |
| `NAVIDROME_ROOT` | `/music` | Navidrome library directory (inside container) |
| `DATA_DIR` | `/data` | Service data (database, artwork cache) |
| `GEMINI_API_KEY` | (required) | Your Gemini API key |
| `GEMINI_MODEL` | `gemini-2.0-flash-lite` | Gemini model to use |
| `SCAN_INTERVAL_SECONDS` | `30` | How often to scan for new files |
| `PORT` | `8090` | Web UI port |
| `TZ` | `America/Los_Angeles` | Timezone |

### Gemini System Instructions

The service includes a default system instruction for Gemini, but you can customize it:

1. Open `app/gemini_client.py`
2. Find the clearly marked section:
   ```python
   # ============================================================================
   # GEMINI SYSTEM INSTRUCTIONS PLACEHOLDER
   # ============================================================================
   ```
3. Replace the `SYSTEM_INSTRUCTIONS` variable with your custom instructions

The service sends exactly this format to Gemini:
```
video_title: <video_title>
channel: <channel>
```

And expects this response:
```
title: <Arabic title>
artist: <Arabic artist>
```

## How It Works

### 1. File Detection
- Service scans `INCOMING_ROOT` recursively every 30 seconds (configurable)
- Looks for files matching: `{{video_title}}###{{channel}}.{{ext}}`
- Example: `زواج الغالي###ملا حاتم العبدالله.mp3`

### 2. Metadata Inference
- Parses filename into `video_title` and `channel`
- Sends to Gemini AI for Arabic metadata extraction
- Receives `title` and `artist` back

### 3. Initial Processing
- Applies metadata using `mutagen`:
  - Title = inferred title
  - Artist = inferred artist
  - Album = "منوعات" (fixed)
  - AlbumArtist = same as artist
  - Genre = (empty until user selects)
- Renames file to `{{title}}.{{ext}}`
- Extracts embedded artwork (if present)
- Adds to review queue

### 4. Web UI Review
- User sees pending items in a grid
- Each item shows:
  - Artwork (if available)
  - Editable title and artist fields
  - Original source (video_title + channel)
  - Genre selection buttons
- User selects genre and optionally edits fields
- Clicks "Confirm" to finalize

### 5. Move to Navidrome
- Updates metadata with selected genre
- Moves file to: `{NAVIDROME_ROOT}/{artist}/منوعات/{title}.{ext}`
- Creates directories as needed
- Handles filename collisions by appending (1), (2), etc.
- Removes from review queue

## Genre Options

The UI provides these preset genre buttons:
- **مواليد وأفراح** (Celebrations & Occasions)
- **لطميات** (Lamentation)
- **شعر** (Poetry)
- **قرآن** (Quran)
- **أخرى…** (Other - opens text input for custom genre)

## File Naming Format

Pinchflat must output files in this exact format:

```
{{video_title}}###{{channel}}.{{ext}}
```

Where:
- `video_title` = The video title
- `###` = Separator (three hash symbols)
- `channel` = The channel name
- `.ext` = File extension (.mp3, .m4a, .flac, .ogg)

**Example**: `زواج الغالي###ملا حاتم العبدالله.mp3`

## Navidrome Library Structure

Files are organized as:

```
{NAVIDROME_ROOT}/
├── {Artist 1}/
│   └── منوعات/
│       ├── {Title 1}.mp3
│       └── {Title 2}.mp3
├── {Artist 2}/
│   └── منوعات/
│       └── {Title 3}.m4a
```

All files go into a "منوعات" (Miscellaneous) album under each artist.

## Development

### Running Locally (Without Docker)

1. **Create virtual environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set environment variables**
   ```bash
   export GEMINI_API_KEY=your_key_here
   export INCOMING_ROOT=/path/to/incoming
   export NAVIDROME_ROOT=/path/to/music
   export DATA_DIR=./data
   ```

4. **Run the service**
   ```bash
   python -m uvicorn app.main:app --reload --port 8090
   ```

5. **Open browser**
   ```
   http://localhost:8090
   ```

## Troubleshooting

### Files Not Being Detected

- Check that files match the naming format: `title###channel.ext`
- Verify `INCOMING_ROOT` path is correct in docker-compose.yml
- Check container logs: `docker-compose logs -f metadata-editor`

### Gemini API Errors

- Verify `GEMINI_API_KEY` is set correctly
- Check API quota/limits in Google Cloud Console
- Review logs for specific error messages

### Metadata Not Applied

- Ensure the audio file is not corrupted
- Check file format is supported (MP3, M4A, FLAC, OGG)
- Verify mutagen can read the file format

### Files Not Moving to Navidrome

- Check `NAVIDROME_ROOT` path exists and is writable
- Verify no permission issues on the destination directory
- Review logs for specific error messages

## Logs

View service logs:
```bash
docker-compose logs -f metadata-editor
```

Logs include:
- File discovery events
- Gemini API requests/responses
- Metadata application results
- File move operations
- Errors and warnings

## Database

The service uses SQLite to track pending items. The database is stored at:
```
{DATA_DIR}/metadata_editor.db
```

This is persisted via Docker volume, so items survive container restarts.

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/pending` | List all pending items |
| POST | `/api/pending/{id}/update` | Update item fields (title, artist, genre) |
| POST | `/api/pending/{id}/confirm` | Confirm and move item to Navidrome |
| GET | `/api/artwork/{id}` | Get artwork image for item |
| GET | `/api/events` | SSE stream for real-time updates |

## License

This project is provided as-is for personal use.

## Support

For issues or questions, check the logs first. Common issues are usually related to:
1. File naming format mismatch
2. Incorrect volume paths in docker-compose.yml
3. Missing or invalid Gemini API key
4. File permission issues
