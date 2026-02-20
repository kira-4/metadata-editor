"""FastAPI routes."""
import logging
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
import asyncio
import json

from app.config import config
from app.database import get_db, DatabaseManager
from app.metadata_processor import metadata_processor
from app.mover import file_mover

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api")

# SSE clients
sse_clients = []


class UpdateItemRequest(BaseModel):
    """Request to update item fields."""
    title: Optional[str] = None
    artist: Optional[str] = None
    genre: Optional[str] = None


class ConfirmItemRequest(BaseModel):
    """Request to confirm and move item."""
    pass


@router.get("/pending/{item_id}/dry-run")
async def dry_run_item(item_id: int, db: Session = Depends(get_db)):
    """Preview metadata write and destination path without modifying files."""
    try:
        item = DatabaseManager.get_item_by_id(db, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")

        title = (item.current_title or "").strip()
        artist = (item.current_artist or "").strip()
        genre = (item.genre or "").strip()

        missing_fields = []
        if not title:
            missing_fields.append("title")
        if not artist:
            missing_fields.append("artist")
        if not genre:
            missing_fields.append("genre")

        preview = file_mover.get_destination_preview(
            artist=artist or "unknown",
            title=title or "untitled",
            extension=item.extension
        )

        current_path = Path(item.current_path)
        file_exists = current_path.exists()
        if not file_exists:
            missing_fields.append("file")

        m4a_atoms = None
        if item.extension.lower() == ".m4a":
            m4a_atoms = {
                "title": {"atom": "©nam", "value": title},
                "artist": {"atom": "©ART", "value": artist},
                "album_artist": {"atom": "aART", "value": artist},
                "album": {"atom": "©alb", "value": title},
                "genre": {"atom": "©gen", "value": genre}
            }

        permission_ok = bool(
            preview.get("navidrome_root_exists")
            and preview.get("navidrome_root_writable")
            and preview.get("destination_parent_writable")
        )

        return {
            "item_id": item.id,
            "can_confirm": len(missing_fields) == 0 and permission_ok,
            "missing_fields": missing_fields,
            "source_path": item.current_path,
            "metadata_preview": {
                "title": title,
                "artist": artist,
                "album_artist": artist,
                "album": title,
                "genre": genre,
                "m4a_atoms": m4a_atoms
            },
            "move_preview": preview
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating dry-run for item {item_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pending")
async def get_pending_items(db: Session = Depends(get_db)):
    """Get all pending items."""
    try:
        items = DatabaseManager.get_pending_items(db)
        return [item.to_dict() for item in items]
    except Exception as e:
        logger.error(f"Error getting pending items: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pending/{item_id}/update")
async def update_item(
    item_id: int,
    request: UpdateItemRequest,
    db: Session = Depends(get_db)
):
    """Update item fields."""
    try:
        update_kwargs = {}

        if request.title is not None:
            title = request.title.strip()
            if len(title) > 300:
                raise HTTPException(status_code=400, detail="العنوان طويل جداً (max 300 chars)")
            update_kwargs["title"] = title

        if request.artist is not None:
            artist = request.artist.strip()
            if len(artist) > 300:
                raise HTTPException(status_code=400, detail="اسم الفنان طويل جداً (max 300 chars)")
            update_kwargs["artist"] = artist

        if request.genre is not None:
            genre = request.genre.strip()
            if genre == "أخرى…":
                raise HTTPException(status_code=400, detail="يرجى إدخال نوع موسيقي محدد")
            if len(genre) > 200:
                raise HTTPException(status_code=400, detail="النوع الموسيقي طويل جداً (max 200 chars)")
            update_kwargs["genre"] = genre

        item = DatabaseManager.update_item(
            db,
            item_id,
            title=update_kwargs.get("title"),
            artist=update_kwargs.get("artist"),
            genre=update_kwargs.get("genre")
        )
        
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Notify SSE clients about the update
        await notify_sse_clients({"type": "item_updated", "id": item_id})
        
        return item.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating item {item_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pending/{item_id}/confirm")
async def confirm_item(
    item_id: int,
    db: Session = Depends(get_db)
):
    """Confirm item: apply final metadata and move to Navidrome."""
    try:
        item = DatabaseManager.get_item_by_id(db, item_id)
        
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Allow pending or error/needs_manual status for retry
        if item.status not in ["pending", "error", "needs_manual"]:
            raise HTTPException(status_code=400, detail=f"Item cannot be confirmed (status: {item.status})")
        
        # Validate required fields with trimming
        if not item.current_title or not item.current_title.strip():
            raise HTTPException(status_code=400, detail="العنوان مطلوب (Title is required)")
        
        if not item.current_artist or not item.current_artist.strip():
            raise HTTPException(status_code=400, detail="اسم الفنان مطلوب (Artist is required)")
        
        if not item.genre or not item.genre.strip():
            raise HTTPException(status_code=400, detail="النوع الموسيقي مطلوب (Genre is required)")
        
        # Additional validation: reject "أخرى…" literal as genre
        if item.genre.strip() == "أخرى…":
            raise HTTPException(status_code=400, detail="يرجى إدخال نوع موسيقي محدد (Please enter a specific genre)")
        
        # Length validation
        if len(item.genre.strip()) > 200:
            raise HTTPException(status_code=400, detail="النوع الموسيقي طويل جداً (Genre too long, max 200 characters)")
        
        title = item.current_title.strip()
        artist = item.current_artist.strip()
        genre = item.genre.strip()

        current_path = Path(item.current_path)
        original_path = Path(item.original_path)
        
        if not current_path.exists():
            raise HTTPException(status_code=404, detail="File not found")
        
        # Apply final metadata with genre
        # First, embed artwork if available
        if item.artwork_path and Path(item.artwork_path).exists():
            try:
                artwork_path = Path(item.artwork_path)
                logger.info(f"Embedding artwork from {artwork_path}")
                
                # Determine mime type
                mime_type = 'image/jpeg'
                if artwork_path.suffix.lower() == '.png':
                    mime_type = 'image/png'
                
                # Read image data
                image_data = artwork_path.read_bytes()
                
                # Embed
                embed_success = metadata_processor.embed_artwork_safe(current_path, image_data, mime_type)
                if not embed_success:
                    logger.warning(f"Artwork embed verification failed for item {item_id}")
            except Exception as e:
                logger.error(f"Failed to embed artwork: {e}")
                # Continue anyway, not critical failure
        
        # Atomic metadata update with roundtrip verification
        success = metadata_processor.update_metadata_safe(
            current_path,
            title=title,
            artist=artist,
            album=title,
            album_artist=artist,
            genre=genre
        )
        
        if not success:
            # Update item with error
            DatabaseManager.update_item_error(db, item_id, "Failed to apply metadata")
            await notify_sse_clients({"type": "item_error", "id": item_id})
            raise HTTPException(status_code=500, detail="Failed to apply metadata")
        
        # Move to Navidrome
        new_path = file_mover.move_to_navidrome(
            current_path,
            artist=artist,
            title=title,
            extension=item.extension
        )
        
        if not new_path:
            # Update item with error
            DatabaseManager.update_item_error(db, item_id, "Failed to move file")
            await notify_sse_clients({"type": "item_error", "id": item_id})
            raise HTTPException(status_code=500, detail="Failed to move file")
        
        # Mark as done
        DatabaseManager.mark_as_done(db, item_id, str(new_path))
        
        # CRITICAL: Clean up original file from /incoming ONLY after successful move
        try:
            if original_path.exists():
                original_path.unlink()
                logger.info(f"Deleted original file from incoming: {original_path}")
        except Exception as e:
            logger.warning(f"Failed to delete original file {original_path}: {e}")
        
        # Clean up staging directory
        try:
            staging_dir = current_path.parent
            # Only delete if it's in staging directory (safety check)
            if staging_dir.is_relative_to(config.STAGING_DIR):
                import shutil
                shutil.rmtree(staging_dir)
                logger.info(f"Cleaned up staging directory: {staging_dir}")
        except Exception as e:
            logger.warning(f"Failed to cleanup staging directory: {e}")
        
        # Notify SSE clients
        await notify_sse_clients({"type": "item_confirmed", "id": item_id})
        
        return {"success": True, "new_path": str(new_path)}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error confirming item {item_id}: {e}")
        # Try to update item with error
        try:
            DatabaseManager.update_item_error(db, item_id, str(e))
            await notify_sse_clients({"type": "item_error", "id": item_id})
        except:
            pass
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/artwork/{item_id}")
async def get_artwork(item_id: int, db: Session = Depends(get_db)):
    """Get artwork for an item."""
    try:
        item = DatabaseManager.get_item_by_id(db, item_id)
        
        if not item or not item.artwork_path:
            raise HTTPException(status_code=404, detail="Artwork not found")
        
        artwork_path = Path(item.artwork_path)
        
        if not artwork_path.exists():
            raise HTTPException(status_code=404, detail="Artwork file not found")
        
        return FileResponse(artwork_path)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting artwork for item {item_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/pending/{item_id}")
async def delete_item(item_id: int, db: Session = Depends(get_db)):
    """Delete a pending item and its files."""
    try:
        item = DatabaseManager.get_item_by_id(db, item_id)
        if not item:
            raise HTTPException(status_code=404, detail="Item not found")
        
        # Paths
        current_path = Path(item.current_path)
        original_path = Path(item.original_path)
        artwork_path = Path(item.artwork_path) if item.artwork_path else None
        
        # 1. Delete staged file (current_path)
        if current_path.exists():
            try:
                current_path.unlink()
                
                # Cleanup staging dir if empty
                staging_dir = current_path.parent
                if staging_dir.is_relative_to(config.STAGING_DIR) and not any(staging_dir.iterdir()):
                    staging_dir.rmdir()
            except Exception as e:
                logger.warning(f"Failed to delete staged file {current_path}: {e}")
                
        # 2. Delete original file (original_path) - to prevent rescan
        if original_path.exists():
            try:
                original_path.unlink()
                logger.info(f"Deleted original file: {original_path}")
            except Exception as e:
                logger.warning(f"Failed to delete original file {original_path}: {e}")
        
        # 3. Delete artwork if exists
        if artwork_path and artwork_path.exists():
            try:
                artwork_path.unlink()
            except Exception as e:
                logger.warning(f"Failed to delete artwork {artwork_path}: {e}")
                
        # 4. Remove from DB
        db.delete(item)
        db.commit()
        
        await notify_sse_clients({"type": "item_deleted", "id": item_id})
        
        return {"success": True}
        
    except Exception as e:
        logger.error(f"Error deleting item {item_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


async def event_generator():
    """SSE event generator."""
    queue = asyncio.Queue()
    sse_clients.append(queue)
    
    try:
        while True:
            data = await queue.get()
            yield f"data: {json.dumps(data)}\n\n"
    except asyncio.CancelledError:
        sse_clients.remove(queue)


@router.get("/events")
async def sse_endpoint():
    """Server-Sent Events endpoint for real-time updates."""
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


async def notify_sse_clients(data: dict):
    """Notify all SSE clients with data."""
    for queue in sse_clients:
        try:
            await queue.put(data)
        except Exception as e:
            logger.error(f"Error notifying SSE client: {e}")
