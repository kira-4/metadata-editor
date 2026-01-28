"""FastAPI main application."""
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import config
from app.database import init_db
from app.scanner import file_scanner
from app.api import router
from app.library_api import library_router

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("Starting Audio Post-Processing Service")
    
    # Ensure directories exist
    config.ensure_directories()
    
    # Initialize database
    init_db()
    logger.info("Database initialized")
    
    # Start file scanner
    file_scanner.start()
    
    yield
    
    # Shutdown
    logger.info("Shutting down Audio Post-Processing Service")
    file_scanner.stop()


app = FastAPI(
    title="Audio Metadata Editor",
    description="Post-processing service for Pinchflat → Navidrome",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(router)
app.include_router(library_router)

# Serve static files
app.mount("/", StaticFiles(directory="app/static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
