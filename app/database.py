"""Database models and operations."""
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Iterable, Optional, List
from sqlalchemy import create_engine, Boolean, Column, Integer, String, DateTime, Text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

from app.config import config

Base = declarative_base()


class PendingItem(Base):
    """Model for pending audio files awaiting review."""
    
    __tablename__ = "pending_items"
    
    id = Column(Integer, primary_key=True)
    original_path = Column(Text, nullable=False)
    current_path = Column(Text, nullable=False)
    video_title = Column(Text, nullable=False)
    channel = Column(Text, nullable=False)
    inferred_title = Column(Text, nullable=True)
    inferred_artist = Column(Text, nullable=True)
    current_title = Column(Text, nullable=True)
    current_artist = Column(Text, nullable=True)
    album_artist = Column(Text, nullable=True)
    genre = Column(String(200), nullable=True)
    extension = Column(String(10), nullable=False)
    artwork_path = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending, processing, done, error, needs_manual, dismissed
    error_message = Column(Text, nullable=True)
    file_identifier = Column(Text, nullable=True, index=True)  # Stable hash for duplicate detection
    raw_gemini_response = Column(Text, nullable=True)  # Raw response for debugging parse failures
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "original_path": self.original_path,
            "current_path": self.current_path,
            "video_title": self.video_title,
            "channel": self.channel,
            "inferred_title": self.inferred_title,
            "inferred_artist": self.inferred_artist,
            "current_title": self.current_title,
            "current_artist": self.current_artist,
            "album_artist": self.album_artist,
            "genre": self.genre,
            "extension": self.extension,
            "artwork_url": f"/api/artwork/{self.id}" if self.artwork_path else None,
            "status": self.status,
            "error_message": self.error_message,
            "raw_gemini_response": self.raw_gemini_response,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class LibraryTrack(Base):
    """Model for indexed library tracks from /music."""
    
    __tablename__ = "library_tracks"
    
    id = Column(Integer, primary_key=True)
    file_path = Column(Text, nullable=False, unique=True, index=True)
    title = Column(Text, nullable=True)
    artist = Column(Text, nullable=True, index=True)
    album = Column(Text, nullable=True, index=True)
    album_artist = Column(Text, nullable=True, index=True)
    genre = Column(Text, nullable=True, index=True)
    year = Column(Integer, nullable=True)
    track_number = Column(Integer, nullable=True)
    disc_number = Column(Integer, nullable=True)
    duration = Column(Integer, nullable=True)  # seconds
    file_size = Column(Integer, nullable=True)  # bytes
    file_modified = Column(DateTime, nullable=True)
    has_artwork = Column(Integer, default=0)  # Boolean as int
    indexed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            "id": self.id,
            "file_path": self.file_path,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "album_artist": self.album_artist,
            "genre": self.genre,
            "year": self.year,
            "track_number": self.track_number,
            "disc_number": self.disc_number,
            "duration": self.duration,
            "file_size": self.file_size,
            "file_modified": self.file_modified.isoformat() if self.file_modified else None,
            "has_artwork": bool(self.has_artwork),
            "indexed_at": self.indexed_at.isoformat() if self.indexed_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class TelegramSettings(Base):
    """Singleton row holding Telegram bot credentials for actionable notifications."""

    __tablename__ = "telegram_settings"

    id = Column(Integer, primary_key=True)  # always 1
    bot_token = Column(Text, nullable=True)
    chat_id = Column(Text, nullable=True)  # supports negative supergroup IDs like -100...
    message_thread_id = Column(Integer, nullable=True)  # optional topic thread
    enabled = Column(Boolean, nullable=False, default=True, server_default="1")  # off = keep creds, send nothing
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class LibraryMeta(Base):
    """Singleton row for library-wide metadata (e.g. last scan timestamp)."""

    __tablename__ = "library_meta"

    id = Column(Integer, primary_key=True)  # always 1
    last_scan_at = Column(DateTime, nullable=True)
    updated_at = Column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )


class LibraryMetaManager:
    """Manager for library metadata stored in the database."""

    @staticmethod
    def get_last_scan_at(db: Session) -> Optional[datetime]:
        """Return the last library scan timestamp, or None if never scanned."""
        row = db.query(LibraryMeta).filter(LibraryMeta.id == 1).first()
        if row and row.last_scan_at:
            return row.last_scan_at
        return None

    @staticmethod
    def set_last_scan_at(db: Session, value: datetime) -> None:
        """Persist the last library scan timestamp."""
        row = db.query(LibraryMeta).filter(LibraryMeta.id == 1).first()
        if row is None:
            row = LibraryMeta(id=1, last_scan_at=value)
            db.add(row)
        else:
            row.last_scan_at = value
        db.commit()
        db.refresh(row)


# Database setup
engine = create_engine(f"sqlite:///{config.DB_PATH}", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Initialize the database."""
    Base.metadata.create_all(bind=engine)
    
    # Migrate existing databases: add new columns if they don't exist
    from sqlalchemy import inspect, text
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns('pending_items')]
    
    with engine.connect() as conn:
        if 'file_identifier' not in columns:
            conn.execute(text('ALTER TABLE pending_items ADD COLUMN file_identifier TEXT'))
            conn.execute(text('CREATE INDEX IF NOT EXISTS idx_file_identifier ON pending_items(file_identifier)'))
            conn.commit()
            import logging
            logging.getLogger(__name__).info("Added file_identifier column to database")
        
        if 'raw_gemini_response' not in columns:
            conn.execute(text('ALTER TABLE pending_items ADD COLUMN raw_gemini_response TEXT'))
            conn.commit()
            import logging
            logging.getLogger(__name__).info("Added raw_gemini_response column to database")

        if 'album_artist' not in columns:
            conn.execute(text('ALTER TABLE pending_items ADD COLUMN album_artist TEXT'))
            conn.commit()
            import logging
            logging.getLogger(__name__).info("Added album_artist column to database")

        telegram_columns = [col['name'] for col in inspector.get_columns('telegram_settings')]
        if 'enabled' not in telegram_columns:
            conn.execute(text('ALTER TABLE telegram_settings ADD COLUMN enabled BOOLEAN NOT NULL DEFAULT 1'))
            conn.commit()
            import logging
            logging.getLogger(__name__).info("Added enabled column to telegram_settings")


def get_db() -> Session:
    """Get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


class DatabaseManager:
    """Manager for database operations."""
    
    @staticmethod
    def create_pending_item(
        db: Session,
        original_path: str,
        current_path: str,
        video_title: str,
        channel: str,
        extension: str,
        inferred_title: Optional[str] = None,
        inferred_artist: Optional[str] = None,
        album_artist: Optional[str] = None,
        genre: Optional[str] = None,
        artwork_path: Optional[str] = None,
        error_message: Optional[str] = None,
        file_identifier: Optional[str] = None,
        raw_gemini_response: Optional[str] = None,
        status: Optional[str] = None
    ) -> PendingItem:
        """Create a new pending item."""
        # Check if item already exists (by file identifier first, then original path)
        if file_identifier:
            existing = db.query(PendingItem).filter(
                PendingItem.file_identifier == file_identifier
            ).first()
            if existing:
                return existing
        
        existing = db.query(PendingItem).filter(
            PendingItem.original_path == original_path
        ).first()
        
        if existing:
            return existing
        
        # Determine status
        if status:
            pass # Use provided status
        elif error_message and raw_gemini_response:
            status = "needs_manual"
        elif error_message:
            status = "error"
        else:
            status = "pending"
        
        item = PendingItem(
            original_path=original_path,
            current_path=current_path,
            video_title=video_title,
            channel=channel,
            inferred_title=inferred_title,
            inferred_artist=inferred_artist,
            album_artist=album_artist,
            current_title=inferred_title,  # Initially same as inferred
            current_artist=inferred_artist,
            genre=(genre or "").strip() or None,  # genre already embedded in the file
            extension=extension,
            artwork_path=artwork_path,
            status=status,
            error_message=error_message,
            file_identifier=file_identifier,
            raw_gemini_response=raw_gemini_response
        )
        db.add(item)
        db.commit()
        db.refresh(item)
        return item
    
    @staticmethod
    def get_pending_items(db: Session) -> List[PendingItem]:
        """Get all pending items (including error/needs_manual for UI display)."""
        return db.query(PendingItem).filter(
            PendingItem.status.in_(["pending", "error", "needs_manual"])
        ).order_by(PendingItem.created_at.desc()).all()
    
    @staticmethod
    def get_item_by_id(db: Session, item_id: int) -> Optional[PendingItem]:
        """Get item by ID."""
        return db.query(PendingItem).filter(PendingItem.id == item_id).first()
    
    @staticmethod
    def update_item(
        db: Session,
        item_id: int,
        title: Optional[str] = None,
        artist: Optional[str] = None,
        album_artist: Optional[str] = None,
        genre: Optional[str] = None
    ) -> Optional[PendingItem]:
        """Update item fields."""
        item = db.query(PendingItem).filter(PendingItem.id == item_id).first()
        if not item:
            return None
        
        if title is not None:
            item.current_title = title
        if artist is not None:
            item.current_artist = artist
        if album_artist is not None:
            item.album_artist = album_artist
        if genre is not None:
            item.genre = genre
        
        item.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(item)
        return item
    
    @staticmethod
    def claim_for_processing(db: Session, item_id: int, from_statuses) -> bool:
        """Atomically move an item to 'processing'. False if another request got it first."""
        claimed = db.query(PendingItem).filter(
            PendingItem.id == item_id,
            PendingItem.status.in_(list(from_statuses)),
        ).update({"status": "processing"}, synchronize_session=False)
        db.commit()
        return claimed == 1

    @staticmethod
    def release_claim(db: Session, item_id: int, status: str) -> None:
        """Return a still-'processing' item to `status` (no-op once done/error was recorded)."""
        db.query(PendingItem).filter(
            PendingItem.id == item_id,
            PendingItem.status == "processing",
        ).update({"status": status}, synchronize_session=False)
        db.commit()

    @staticmethod
    def reset_interrupted_processing(db: Session) -> int:
        """At startup: items left 'processing' by a crash become retryable errors."""
        count = db.query(PendingItem).filter(PendingItem.status == "processing").update(
            {"status": "error", "error_message": "Interrupted while moving - please retry"},
            synchronize_session=False,
        )
        db.commit()
        return count

    @staticmethod
    def update_item_error(
        db: Session,
        item_id: int,
        error_message: str,
        status: str = "error"
    ) -> Optional[PendingItem]:
        """Update item with error."""
        item = db.query(PendingItem).filter(PendingItem.id == item_id).first()
        if not item:
            return None
        
        item.status = status
        item.error_message = error_message
        item.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(item)
        return item
    
    @staticmethod
    def mark_as_done(db: Session, item_id: int, new_path: str) -> Optional[PendingItem]:
        """Mark item as done and update path."""
        item = db.query(PendingItem).filter(PendingItem.id == item_id).first()
        if not item:
            return None
        
        item.status = "done"
        item.current_path = new_path
        item.error_message = None  # Clear any previous errors
        item.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(item)
        return item
    
    @staticmethod
    def file_already_processed(db: Session, file_path: str) -> bool:
        """Check if a file has already been processed."""
        return db.query(PendingItem).filter(
            PendingItem.original_path == file_path
        ).first() is not None

    @staticmethod
    def item_exists_for_path(db: Session, current_path: str) -> bool:
        """Check if any queue item references this current (staged) path."""
        return db.query(PendingItem).filter(
            PendingItem.current_path == current_path
        ).first() is not None

    @staticmethod
    def get_item_by_identifier(db: Session, file_identifier: str) -> Optional[PendingItem]:
        """Get item by file identifier."""
        return db.query(PendingItem).filter(
            PendingItem.file_identifier == file_identifier
        ).first()

    @staticmethod
    def mark_as_dismissed(db: Session, item_id: int, trash_path: str) -> None:
        """Hide an item from the queue; its original now lives at trash_path."""
        db.query(PendingItem).filter(PendingItem.id == item_id).update(
            {"status": "dismissed", "current_path": trash_path, "artwork_path": None,
             "updated_at": datetime.now(timezone.utc)},
            synchronize_session=False,
        )
        db.commit()

    @staticmethod
    def forget_dismissed(db: Session, file_identifier: str, original_path: str) -> int:
        """Drop dismissed rows for a file that is back in /incoming, so it re-imports.

        Their trash dirs go too: the file is in /incoming again, and ids get reused.
        """
        rows = db.query(PendingItem).filter(
            PendingItem.status == "dismissed",
            (PendingItem.file_identifier == file_identifier) | (PendingItem.original_path == original_path),
        ).all()
        for row in rows:
            shutil.rmtree(config.TRASH_DIR / str(row.id), ignore_errors=True)
            db.delete(row)
        db.commit()
        return len(rows)

    @staticmethod
    def purge_expired_trash(db: Session) -> int:
        """Delete trashed originals (and their rows) older than TRASH_RETENTION_DAYS."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=config.TRASH_RETENTION_DAYS)
        expired = db.query(PendingItem).filter(
            PendingItem.status == "dismissed", PendingItem.updated_at < cutoff
        ).all()
        for item in expired:
            shutil.rmtree(config.TRASH_DIR / str(item.id), ignore_errors=True)
            db.delete(item)
        db.commit()
        return len(expired)


class LibraryManager:
    """Manager for library database operations."""
    
    @staticmethod
    def create_or_update_track(
        db: Session,
        file_path: str,
        metadata: dict,
        file_stats: dict
    ) -> LibraryTrack:
        """Create or update a library track."""
        track = db.query(LibraryTrack).filter(
            LibraryTrack.file_path == file_path
        ).first()
        
        if track:
            # Update existing track
            track.title = metadata.get('title')
            track.artist = metadata.get('artist')
            track.album = metadata.get('album')
            track.album_artist = metadata.get('album_artist')
            track.genre = metadata.get('genre')
            track.year = metadata.get('year')
            track.track_number = metadata.get('track_number')
            track.disc_number = metadata.get('disc_number')
            track.duration = metadata.get('duration')
            track.has_artwork = 1 if metadata.get('has_artwork') else 0
            track.file_size = file_stats.get('size')
            track.file_modified = file_stats.get('modified')
            track.updated_at = datetime.now(timezone.utc)
        else:
            # Create new track
            track = LibraryTrack(
                file_path=file_path,
                title=metadata.get('title'),
                artist=metadata.get('artist'),
                album=metadata.get('album'),
                album_artist=metadata.get('album_artist'),
                genre=metadata.get('genre'),
                year=metadata.get('year'),
                track_number=metadata.get('track_number'),
                disc_number=metadata.get('disc_number'),
                duration=metadata.get('duration'),
                has_artwork=1 if metadata.get('has_artwork') else 0,
                file_size=file_stats.get('size'),
                file_modified=file_stats.get('modified')
            )
            db.add(track)
        
        db.commit()
        db.refresh(track)
        return track
    
    @staticmethod
    def get_track_by_id(db: Session, track_id: int) -> Optional[LibraryTrack]:
        """Get track by ID."""
        return db.query(LibraryTrack).filter(LibraryTrack.id == track_id).first()
    
    @staticmethod
    def get_track_by_path(db: Session, file_path: str) -> Optional[LibraryTrack]:
        """Get track by file path."""
        return db.query(LibraryTrack).filter(LibraryTrack.file_path == file_path).first()
    
    @staticmethod
    def delete_track(db: Session, track_id: int) -> bool:
        """Delete a track from the library."""
        track = db.query(LibraryTrack).filter(LibraryTrack.id == track_id).first()
        if track:
            db.delete(track)
            db.commit()
            return True
        return False
    
    @staticmethod
    def delete_track_by_path(db: Session, file_path: str) -> bool:
        """Delete a track by file path (for cleanup when file is removed)."""
        track = db.query(LibraryTrack).filter(LibraryTrack.file_path == file_path).first()
        if track:
            db.delete(track)
            db.commit()
            return True
        return False
    
    @staticmethod
    def update_track_metadata(
        db: Session,
        track_id: int,
        title: Optional[str] = None,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        album_artist: Optional[str] = None,
        genre: Optional[str] = None,
        year: Optional[int] = None,
        track_number: Optional[int] = None,
        disc_number: Optional[int] = None,
        clear: Iterable[str] = ()
    ) -> Optional[LibraryTrack]:
        """Update track metadata fields. None leaves a field as is; names in `clear` are set to NULL."""
        track = db.query(LibraryTrack).filter(LibraryTrack.id == track_id).first()
        if not track:
            return None
        
        if title is not None:
            track.title = title
        if artist is not None:
            track.artist = artist
        if album is not None:
            track.album = album
        if album_artist is not None:
            track.album_artist = album_artist
        if genre is not None:
            track.genre = genre
        if year is not None:
            track.year = year
        if track_number is not None:
            track.track_number = track_number
        if disc_number is not None:
            track.disc_number = disc_number
        for field in clear:
            setattr(track, field, None)
        
        track.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(track)
        return track
    
    @staticmethod
    def _split_artists(value: Optional[str]) -> List[str]:
        """Split a semicolon-delimited artist string into individual artist names."""
        if not value or not value.strip():
            return []
        return [a.strip() for a in value.split(';') if a.strip()]

    @staticmethod
    def _artist_match_filter(field, artist_name):
        """Generate SQLAlchemy OR filter for matching an artist in a semicolon-delimited field.

        Handles both ';' and '; ' separators so that multi-artist values like
        "ArtistA; ArtistB" correctly match individual artist names.
        """
        from sqlalchemy import or_
        n = artist_name
        return or_(
            field == n,
            field.like(f'{n};%'),
            field.like(f'{n} ;%'),
            field.like(f'%;{n}'),
            field.like(f'%; {n}'),
            field.like(f'%;{n};%'),
            field.like(f'%; {n};%'),
            field.like(f'%;{n} ;%'),
        )

    @staticmethod
    def get_all_artists(db: Session, search: Optional[str] = None) -> List[dict]:
        """Get all unique individual artists with track and album counts.

        Splits semicolon-delimited artist strings so that each individual artist
        appears as a separate entry, with aggregated counts across all their tracks.
        """
        from collections import defaultdict

        # Fetch all tracks with artist and album_artist
        rows = db.query(
            LibraryTrack.artist,
            LibraryTrack.album_artist,
            LibraryTrack.album,
            LibraryTrack.id
        ).filter(
            (LibraryTrack.artist.isnot(None)) | (LibraryTrack.album_artist.isnot(None))
        ).all()

        # Accumulate per-individual-artist counts
        track_counts: Dict[str, int] = defaultdict(int)
        album_sets: Dict[str, set] = defaultdict(set)

        for row in rows:
            # A track counts once per artist, even when it is both artist and album artist
            names = set(LibraryManager._split_artists(row.artist or ""))
            names |= set(LibraryManager._split_artists(row.album_artist or ""))
            for name in names:
                track_counts[name] += 1
                if row.album:
                    album_sets[name].add((row.album, row.album_artist))

        # Build result list
        all_names = set(track_counts.keys())
        if search:
            needle = search.lower()
            all_names = {n for n in all_names if needle in n.lower()}

        return [
            {
                'name': name,
                'track_count': track_counts[name],
                'album_count': len(album_sets.get(name, set()))
            }
            for name in sorted(all_names)
        ]

    @staticmethod
    def get_artist_candidates(db: Session) -> List[dict]:
        """
        Get merged distinct artist names for fuzzy suggestion.

        Sources:
        - library_tracks.artist
        - library_tracks.album_artist

        Returns:
        [
            {
                "name": "<artist>",
                "track_count": <int frequency from both sources>
            },
            ...
        ]
        """
        from sqlalchemy import func

        merged: Dict[str, int] = {}

        artist_rows = (
            db.query(
                LibraryTrack.artist.label("name"),
                func.count(LibraryTrack.id).label("track_count")
            )
            .filter(LibraryTrack.artist.isnot(None))
            .group_by(LibraryTrack.artist)
            .all()
        )

        for row in artist_rows:
            name = (row.name or "").strip()
            if not name:
                continue
            for individual in LibraryManager._split_artists(name):
                merged[individual] = merged.get(individual, 0) + int(row.track_count or 0)

        album_artist_rows = (
            db.query(
                LibraryTrack.album_artist.label("name"),
                func.count(LibraryTrack.id).label("track_count")
            )
            .filter(LibraryTrack.album_artist.isnot(None))
            .group_by(LibraryTrack.album_artist)
            .all()
        )

        for row in album_artist_rows:
            name = (row.name or "").strip()
            if not name:
                continue
            for individual in LibraryManager._split_artists(name):
                merged[individual] = merged.get(individual, 0) + int(row.track_count or 0)

        return [
            {"name": name, "track_count": track_count}
            for name, track_count in sorted(
                merged.items(),
                key=lambda item: (item[1], -len(item[0]), item[0]),
                reverse=True,
            )
        ]
    
    @staticmethod
    def get_all_albums(db: Session, search: Optional[str] = None, artist: Optional[str] = None) -> List[dict]:
        """Get all unique albums with metadata."""
        from sqlalchemy import func
        
        from sqlalchemy import case

        # Album identity is (album, album_artist); year is shown, not part of the key
        query = db.query(
            LibraryTrack.album,
            LibraryTrack.album_artist,
            func.max(LibraryTrack.year).label('year'),
            func.count(LibraryTrack.id).label('track_count'),
            # Sample only tracks that really carry artwork
            func.max(case((LibraryTrack.has_artwork == 1, LibraryTrack.id))).label('artwork_id')
        ).filter(LibraryTrack.album.isnot(None))
        
        if search:
            query = query.filter(LibraryTrack.album.like(LibraryManager._like_pattern(search), escape="\\"))
        
        if artist:
            from sqlalchemy import or_
            query = query.filter(
                or_(
                    LibraryManager._artist_match_filter(LibraryTrack.artist, artist),
                    LibraryManager._artist_match_filter(LibraryTrack.album_artist, artist),
                )
            )
        
        query = query.group_by(LibraryTrack.album, LibraryTrack.album_artist)
        
        results = query.all()
        return [
            {
                'name': r.album,
                'album_artist': r.album_artist,
                'year': r.year,
                'track_count': r.track_count,
                'has_artwork': r.artwork_id is not None,
                'artwork_id': r.artwork_id
            }
            for r in results
        ]
    
    @staticmethod
    def get_all_genres(db: Session, search: Optional[str] = None) -> List[dict]:
        """Get all unique genres with track counts."""
        from sqlalchemy import func
        
        query = db.query(
            LibraryTrack.genre,
            func.count(LibraryTrack.id).label('track_count')
        ).filter(LibraryTrack.genre.isnot(None))
        
        if search:
            query = query.filter(LibraryTrack.genre.like(LibraryManager._like_pattern(search), escape="\\"))
        
        query = query.group_by(LibraryTrack.genre)
        
        results = query.all()
        return [
            {
                'name': r.genre,
                'track_count': r.track_count
            }
            for r in results
        ]
    
    TRACK_SORT_COLUMNS = {
        "title": LibraryTrack.title,
        "artist": LibraryTrack.artist,
        "album": LibraryTrack.album,
        "year": LibraryTrack.year,
        "track_number": LibraryTrack.track_number,
    }

    @staticmethod
    def _like_pattern(value: str) -> str:
        """Substring LIKE pattern with %, _ and \\ matched literally (use escape='\\')."""
        escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
        return f"%{escaped}%"

    @staticmethod
    def _filtered_tracks(
        db: Session,
        search: Optional[str] = None,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        genre: Optional[str] = None,
        album_artist: Optional[str] = None,
    ):
        """One filtered query shared by listing and counting, so totals always match."""
        from sqlalchemy import or_

        query = db.query(LibraryTrack)

        if search:
            pattern = LibraryManager._like_pattern(search)
            query = query.filter(or_(
                LibraryTrack.title.like(pattern, escape="\\"),
                LibraryTrack.artist.like(pattern, escape="\\"),
                LibraryTrack.album.like(pattern, escape="\\"),
            ))

        if artist:
            query = query.filter(
                or_(
                    LibraryManager._artist_match_filter(LibraryTrack.artist, artist),
                    LibraryManager._artist_match_filter(LibraryTrack.album_artist, artist),
                )
            )

        if album:
            query = query.filter(LibraryTrack.album == album)

        if album_artist == "":
            # Albums listed without an album artist (NULL or empty)
            query = query.filter(or_(LibraryTrack.album_artist.is_(None), LibraryTrack.album_artist == ""))
        elif album_artist is not None:
            query = query.filter(LibraryTrack.album_artist == album_artist)

        if genre:
            query = query.filter(LibraryTrack.genre == genre)

        return query

    @staticmethod
    def get_tracks(
        db: Session,
        search: Optional[str] = None,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        genre: Optional[str] = None,
        album_artist: Optional[str] = None,
        sort_by: str = "artist",
        sort_order: str = "asc",
        limit: int = 100,
        offset: int = 0
    ) -> List[LibraryTrack]:
        """Get tracks with optional filters, sorted in SQL *before* pagination."""
        from sqlalchemy import func

        query = LibraryManager._filtered_tracks(db, search, artist, album, genre, album_artist)

        column = LibraryManager.TRACK_SORT_COLUMNS.get(sort_by, LibraryTrack.artist)
        if sort_by in ("year", "track_number"):
            key = func.coalesce(column, 0)
        else:
            key = func.lower(func.coalesce(column, ""))
        key = key.desc() if sort_order == "desc" else key.asc()

        # Stable secondary order, then id as a unique tiebreaker so pages never overlap
        query = query.order_by(
            key,
            func.lower(func.coalesce(LibraryTrack.album, "")),
            func.coalesce(LibraryTrack.track_number, 0),
            LibraryTrack.id,
        )
        return query.limit(limit).offset(offset).all()

    @staticmethod
    def count_tracks(
        db: Session,
        search: Optional[str] = None,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        genre: Optional[str] = None,
        album_artist: Optional[str] = None,
    ) -> int:
        """Count tracks matching the same filters as get_tracks."""
        return LibraryManager._filtered_tracks(db, search, artist, album, genre, album_artist).count()

    @staticmethod
    def get_total_track_count(db: Session) -> int:
        """Get total number of tracks in library."""
        return db.query(LibraryTrack).count()
    
    @staticmethod
    def clear_library(db: Session) -> int:
        """Clear all library tracks. Returns number of deleted tracks."""
        count = db.query(LibraryTrack).count()
        db.query(LibraryTrack).delete()
        db.commit()
        return count


class SettingsManager:
    """Manager for application settings stored in the database."""

    @staticmethod
    def get_telegram_settings(db: Session) -> TelegramSettings:
        """Return the singleton Telegram settings row, creating an empty one on first call."""
        settings = db.query(TelegramSettings).filter(TelegramSettings.id == 1).first()
        if settings is None:
            settings = TelegramSettings(id=1, bot_token=None, chat_id=None, message_thread_id=None)
            db.add(settings)
            db.commit()
            db.refresh(settings)
        return settings

    @staticmethod
    def update_telegram_settings(
        db: Session,
        bot_token: Optional[str] = None,
        chat_id: Optional[str] = None,
        message_thread_id: Optional[int] = None,
        update_bot_token: bool = True,
        enabled: Optional[bool] = None,
    ) -> TelegramSettings:
        """
        Update the singleton Telegram settings row.

        When update_bot_token is False, the existing bot_token is preserved
        regardless of the `bot_token` argument — lets the UI submit a blank
        token field to mean "leave it alone".
        """
        settings = SettingsManager.get_telegram_settings(db)

        if update_bot_token:
            settings.bot_token = bot_token

        settings.chat_id = chat_id
        settings.message_thread_id = message_thread_id
        if enabled is not None:
            settings.enabled = enabled
        settings.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(settings)
        return settings

    @staticmethod
    def clear_telegram_settings(db: Session) -> TelegramSettings:
        """Disconnect: forget the token, chat and topic."""
        settings = SettingsManager.get_telegram_settings(db)
        settings.bot_token = None
        settings.chat_id = None
        settings.message_thread_id = None
        settings.enabled = True
        settings.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(settings)
        return settings
