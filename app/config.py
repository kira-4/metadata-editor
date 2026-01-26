"""Configuration settings from environment variables."""
import os
from pathlib import Path


class Config:
    """Application configuration."""
    
    # Directory paths
    INCOMING_ROOT = Path(os.getenv("INCOMING_ROOT", "/incoming"))
    NAVIDROME_ROOT = Path(os.getenv("NAVIDROME_ROOT", "/music"))
    DATA_DIR = Path(os.getenv("DATA_DIR", "/data"))
    
    # Gemini API
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash-lite")
    
    # Scanner settings
    SCAN_INTERVAL_SECONDS = int(os.getenv("SCAN_INTERVAL_SECONDS", "30"))
    
    # Web server
    PORT = int(os.getenv("PORT", "8090"))
    HOST = os.getenv("HOST", "0.0.0.0")
    
    # Supported audio formats
    AUDIO_EXTENSIONS = {".mp3", ".m4a", ".flac", ".ogg"}
    
    # Fixed metadata values
    ALBUM_NAME = "منوعات"
    
    # Database path
    DB_PATH = DATA_DIR / "metadata_editor.db"
    
    # Artwork cache directory
    ARTWORK_DIR = DATA_DIR / "artwork"
    
    @classmethod
    def ensure_directories(cls):
        """Ensure all required directories exist."""
        cls.DATA_DIR.mkdir(parents=True, exist_ok=True)
        cls.ARTWORK_DIR.mkdir(parents=True, exist_ok=True)


config = Config()
