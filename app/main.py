"""FastAPI main application."""
import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from app.config import config
from app.database import init_db, SessionLocal, DatabaseManager
from app.events import set_loop
from app.scanner import file_scanner
from app.api import router
from app.library_api import library_router
from app.settings_api import settings_router

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
    logger.info(f"Starting {config.APP_NAME}")
    
    # Ensure directories exist
    config.ensure_directories()
    
    # Initialize database
    init_db()
    logger.info("Database initialized")

    db = SessionLocal()
    try:
        interrupted = DatabaseManager.reset_interrupted_processing(db)
        if interrupted:
            logger.warning(f"Reset {interrupted} item(s) interrupted mid-move to error")
    finally:
        db.close()

    # Let threads (routes, scanner) publish SSE events onto this loop
    set_loop(asyncio.get_running_loop())
    
    # Start file scanner
    file_scanner.start()
    
    yield
    
    # Shutdown
    logger.info(f"Shutting down {config.APP_NAME}")
    file_scanner.stop()


app = FastAPI(
    title=config.APP_NAME,
    description=config.APP_DESCRIPTION,
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware — wildcard origin is incompatible with allow_credentials=True per the
# CORS spec, so credentials are disabled. This app has no cookie/session auth, so this
# has no functional impact.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API router
app.include_router(router)
app.include_router(library_router)
app.include_router(settings_router)

class RevalidatingStaticFiles(StaticFiles):
    """Static files that browsers must revalidate (cheap 304 via ETag), so a
    redeploy reaches phones immediately instead of serving stale JS/CSS."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers["Cache-Control"] = "no-cache"
        return response


# Serve static files
app.mount("/", RevalidatingStaticFiles(directory="app/static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.HOST, port=config.PORT)
