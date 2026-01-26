"""Database models and operations."""
from datetime import datetime
from pathlib import Path
from typing import Optional, List
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
        raw_gemini_response: Optional[str] = None
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
        
        # Determine status based on error_message and raw_gemini_response
        if error_message and raw_gemini_response:
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
