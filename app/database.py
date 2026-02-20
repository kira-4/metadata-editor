"""Database models and operations."""
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, List
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

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
    genre = Column(String(200), nullable=True)
    extension = Column(String(10), nullable=False)
    artwork_path = Column(Text, nullable=True)
    status = Column(String(20), default="pending")  # pending, done, error, needs_manual
    error_message = Column(Text, nullable=True)
    file_identifier = Column(Text, nullable=True, index=True)  # Stable hash for duplicate detection
    raw_gemini_response = Column(Text, nullable=True)  # Raw response for debugging parse failures
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
    indexed_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
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
            current_title=inferred_title,  # Initially same as inferred
            current_artist=inferred_artist,
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
        if genre is not None:
            item.genre = genre
        
        item.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(item)
        return item
    
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
        item.updated_at = datetime.utcnow()
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
        item.updated_at = datetime.utcnow()
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
    def get_item_by_identifier(db: Session, file_identifier: str) -> Optional[PendingItem]:
        """Get item by file identifier."""
        return db.query(PendingItem).filter(
            PendingItem.file_identifier == file_identifier
        ).first()


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
            track.updated_at = datetime.utcnow()
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
        disc_number: Optional[int] = None
    ) -> Optional[LibraryTrack]:
        """Update track metadata fields."""
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
        
        track.updated_at = datetime.utcnow()
        db.commit()
        db.refresh(track)
        return track
    
    @staticmethod
    def get_all_artists(db: Session, search: Optional[str] = None) -> List[dict]:
        """Get all unique artists with track and album counts."""
        from sqlalchemy import func, distinct
        
        query = db.query(
            LibraryTrack.artist,
            func.count(LibraryTrack.id).label('track_count'),
            func.count(distinct(LibraryTrack.album)).label('album_count')
        ).filter(LibraryTrack.artist.isnot(None))
        
        if search:
            query = query.filter(LibraryTrack.artist.like(f'%{search}%'))
        
        query = query.group_by(LibraryTrack.artist)
        
        results = query.all()
        return [
            {
                'name': r.artist,
                'track_count': r.track_count,
                'album_count': r.album_count
            }
            for r in results
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
            merged[name] = merged.get(name, 0) + int(row.track_count or 0)

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
            merged[name] = merged.get(name, 0) + int(row.track_count or 0)

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
        
        query = db.query(
            LibraryTrack.album,
            LibraryTrack.album_artist,
            LibraryTrack.year,
            func.count(LibraryTrack.id).label('track_count'),
            func.max(LibraryTrack.has_artwork).label('has_artwork'),
            func.max(LibraryTrack.id).label('sample_id')
        ).filter(LibraryTrack.album.isnot(None))
        
        if search:
            query = query.filter(LibraryTrack.album.like(f'%{search}%'))
        
        if artist:
            query = query.filter(
                (LibraryTrack.artist == artist) | (LibraryTrack.album_artist == artist)
            )
        
        query = query.group_by(LibraryTrack.album, LibraryTrack.album_artist, LibraryTrack.year)
        
        results = query.all()
        return [
            {
                'name': r.album,
                'album_artist': r.album_artist,
                'year': r.year,
                'track_count': r.track_count,
                'has_artwork': bool(r.has_artwork),
                'artwork_id': r.sample_id if r.has_artwork else None
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
            query = query.filter(LibraryTrack.genre.like(f'%{search}%'))
        
        query = query.group_by(LibraryTrack.genre)
        
        results = query.all()
        return [
            {
                'name': r.genre,
                'track_count': r.track_count
            }
            for r in results
        ]
    
    @staticmethod
    def get_tracks(
        db: Session,
        search: Optional[str] = None,
        artist: Optional[str] = None,
        album: Optional[str] = None,
        genre: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[LibraryTrack]:
        """Get tracks with optional filters."""
        query = db.query(LibraryTrack)
        
        if search:
            query = query.filter(
                (LibraryTrack.title.like(f'%{search}%')) |
                (LibraryTrack.artist.like(f'%{search}%')) |
                (LibraryTrack.album.like(f'%{search}%'))
            )
        
        if artist:
            query = query.filter(LibraryTrack.artist == artist)
        
        if album:
            query = query.filter(LibraryTrack.album == album)
        
        if genre:
            query = query.filter(LibraryTrack.genre == genre)
        
        query = query.order_by(LibraryTrack.artist, LibraryTrack.album, LibraryTrack.track_number)
        query = query.limit(limit).offset(offset)
        
        return query.all()
    
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
