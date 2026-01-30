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
        item = DatabaseManager.update_item(
            db,
            item_id,
            title=request.title,
            artist=request.artist,
            genre=request.genre
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
                metadata_processor.embed_artwork_safe(current_path, image_data, mime_type)
            except Exception as e:
                logger.error(f"Failed to embed artwork: {e}")
                # Continue anyway, not critical failure
        
        success = metadata_processor.apply_metadata(
            current_path,
            title=item.current_title,
            artist=item.current_artist,
            album=item.current_title,
            genre=item.genre
        )
        
        if not success:
            # Update item with error
            DatabaseManager.update_item_error(db, item_id, "Failed to apply metadata")
            await notify_sse_clients({"type": "item_error", "id": item_id})
            raise HTTPException(status_code=500, detail="Failed to apply metadata")
        
        # Move to Navidrome
        new_path = file_mover.move_to_navidrome(
            current_path,
            artist=item.current_artist,
            title=item.current_title,
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

