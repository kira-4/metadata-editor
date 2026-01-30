"""Library API routes for browsing and editing the music library."""
import logging
from pathlib import Path
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import config
from app.database import get_db, LibraryManager, LibraryTrack
from app.metadata_processor import metadata_processor
from app.library_scanner import library_scanner

logger = logging.getLogger(__name__)

library_router = APIRouter(prefix="/api/library")


# Request/Response models
class UpdateTrackRequest(BaseModel):
    """Request to update track metadata."""
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    album_artist: Optional[str] = None
    genre: Optional[str] = None
    year: Optional[int] = None
    track_number: Optional[int] = None
    disc_number: Optional[int] = None


class BatchUpdateRequest(BaseModel):
    """Request to batch update tracks."""
    track_ids: List[int]
    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None
    album_artist: Optional[str] = None
    genre: Optional[str] = None
    year: Optional[int] = None


class BatchUpdateResult(BaseModel):
    """Result of batch update operation."""
    total: int
    successful: int
    failed: int
    errors: List[dict]


# Browse endpoints
@library_router.get("/artists")
async def get_artists(
    search: Optional[str] = None,
    sort_by: str = "name",  # name, track_count, album_count
    sort_order: str = "asc",  # asc, desc
    db: Session = Depends(get_db)
):
    """Get all artists with track and album counts."""
    try:
        artists = LibraryManager.get_all_artists(db, search=search)
        
        # Sort
        reverse = (sort_order == "desc")
        if sort_by == "name":
            artists.sort(key=lambda x: (x['name'] or '').lower(), reverse=reverse)
        elif sort_by == "track_count":
            artists.sort(key=lambda x: x['track_count'], reverse=reverse)
        elif sort_by == "album_count":
            artists.sort(key=lambda x: x['album_count'], reverse=reverse)
        
        return {
            "artists": artists,
            "total": len(artists)
        }
    except Exception as e:
        logger.error(f"Error getting artists: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@library_router.get("/albums")
async def get_albums(
    search: Optional[str] = None,
    artist: Optional[str] = None,
    sort_by: str = "name",  # name, year, track_count,artist
    sort_order: str = "asc",
    db: Session = Depends(get_db)
):
    """Get all albums."""
    try:
        albums = LibraryManager.get_all_albums(db, search=search, artist=artist)
        
        # Sort
        reverse = (sort_order == "desc")
        if sort_by == "name":
            albums.sort(key=lambda x: (x['name'] or '').lower(), reverse=reverse)
        elif sort_by == "year":
            albums.sort(key=lambda x: x['year'] or 0, reverse=reverse)
        elif sort_by == "track_count":
            albums.sort(key=lambda x: x['track_count'], reverse=reverse)
        elif sort_by == "artist":
            albums.sort(key=lambda x: (x['album_artist'] or '').lower(), reverse=reverse)
        
        return {
            "albums": albums,
            "total": len(albums)
        }
    except Exception as e:
        logger.error(f"Error getting albums: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@library_router.get("/genres")
async def get_genres(
    search: Optional[str] = None,
    sort_by: str = "name",  # name, track_count
    sort_order: str = "asc",
    db: Session = Depends(get_db)
):
    """Get all genres."""
    try:
        genres = LibraryManager.get_all_genres(db, search=search)
        
        # Sort
        reverse = (sort_order == "desc")
        if sort_by == "name":
            genres.sort(key=lambda x: (x['name'] or '').lower(), reverse=reverse)
        elif sort_by == "track_count":
            genres.sort(key=lambda x: x['track_count'], reverse=reverse)
        
        return {
            "genres": genres,
            "total": len(genres)
        }
    except Exception as e:
        logger.error(f"Error getting genres: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@library_router.get("/tracks")
async def get_tracks(
    search: Optional[str] = None,
    artist: Optional[str] = None,
    album: Optional[str] = None,
    genre: Optional[str] = None,
    sort_by: str = "artist",  # title, artist, album, year, track_number
    sort_order: str = "asc",
    limit: int = Query(100, le=500),
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get tracks with optional filters."""
    try:
        tracks = LibraryManager.get_tracks(
            db,
            search=search,
            artist=artist,
            album=album,
            genre=genre,
            limit=limit,
            offset=offset
        )
        
        # Custom sorting if needed
        track_dicts = [t.to_dict() for t in tracks]
        reverse = (sort_order == "desc")
        
        if sort_by == "title":
            track_dicts.sort(key=lambda x: (x['title'] or '').lower(), reverse=reverse)
        elif sort_by == "artist":
            track_dicts.sort(key=lambda x: (x['artist'] or '').lower(), reverse=reverse)
        elif sort_by == "album":
            track_dicts.sort(key=lambda x: (x['album'] or '').lower(), reverse=reverse)
        elif sort_by == "year":
            track_dicts.sort(key=lambda x: x['year'] or 0, reverse=reverse)
        elif sort_by == "track_number":
            track_dicts.sort(key=lambda x: x['track_number'] or 0, reverse=reverse)
        
        total_count = LibraryManager.get_total_track_count(db)
        
        return {
            "tracks": track_dicts,
            "total": total_count,
            "limit": limit,
            "offset": offset
        }
    except Exception as e:
        logger.error(f"Error getting tracks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@library_router.get("/tracks/{track_id}")
async def get_track(track_id: int, db: Session = Depends(get_db)):
    """Get single track details."""
    try:
        track = LibraryManager.get_track_by_id(db, track_id)
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")
        
        return track.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting track {track_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Metadata update endpoints
@library_router.post("/tracks/{track_id}/update")
async def update_track(
    track_id: int,
    request: UpdateTrackRequest,
    db: Session = Depends(get_db)
):
    """Update single track metadata."""
    try:
        track = LibraryManager.get_track_by_id(db, track_id)
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")
        
        file_path = Path(track.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Track file not found")
        
        # Build update kwargs
        update_kwargs = {}
        if request.title is not None:
            update_kwargs['title'] = request.title
        if request.artist is not None:
            update_kwargs['artist'] = request.artist
        if request.album is not None:
            update_kwargs['album'] = request.album
        if request.album_artist is not None:
            update_kwargs['album_artist'] = request.album_artist
        elif request.artist is not None:
            # Sync album_artist with artist if artist is updated but album_artist is not
            update_kwargs['album_artist'] = request.artist
        if request.genre is not None:
            update_kwargs['genre'] = request.genre
        if request.year is not None:
            update_kwargs['year'] = request.year
        if request.track_number is not None:
            update_kwargs['track_number'] = request.track_number
        if request.disc_number is not None:
            update_kwargs['disc_number'] = request.disc_number
        
        # Update file metadata
        success = metadata_processor.update_metadata_safe(file_path, **update_kwargs)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to update file metadata")
        
        # Update database
        updated_track = LibraryManager.update_track_metadata(db, track_id, **update_kwargs)
        
        return {
            "success": True,
            "track": updated_track.to_dict() if updated_track else None
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating track {track_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@library_router.post("/tracks/batch-update")
async def batch_update_tracks(
    request: BatchUpdateRequest,
    db: Session = Depends(get_db)
):
    """Batch update multiple tracks."""
    try:
        if not request.track_ids:
            raise HTTPException(status_code=400, detail="No tracks specified")
        
        results = {
            "total": len(request.track_ids),
            "successful": 0,
            "failed": 0,
            "errors": []
        }
        
        # Build update kwargs
        update_kwargs = {}
        if request.title is not None:
            update_kwargs['title'] = request.title
        if request.artist is not None:
            update_kwargs['artist'] = request.artist
        if request.album is not None:
            update_kwargs['album'] = request.album
        if request.album_artist is not None:
            update_kwargs['album_artist'] = request.album_artist
        elif request.artist is not None:
            # Sync album_artist with artist if artist is updated but album_artist is not
            update_kwargs['album_artist'] = request.artist
        if request.genre is not None:
            update_kwargs['genre'] = request.genre
        if request.year is not None:
            update_kwargs['year'] = request.year
        
        # Process each track
        for track_id in request.track_ids:
            try:
                track = LibraryManager.get_track_by_id(db, track_id)
                if not track:
                    results["failed"] += 1
                    results["errors"].append({
                        "track_id": track_id,
                        "error": "Track not found"
                    })
                    continue
                
                file_path = Path(track.file_path)
                if not file_path.exists():
                    results["failed"] += 1
                    results["errors"].append({
                        "track_id": track_id,
                        "file_path": str(file_path),
                        "error": "File not found"
                    })
                    continue
                
                # Update file metadata
                success = metadata_processor.update_metadata_safe(file_path, **update_kwargs)
                
                if not success:
                    results["failed"] += 1
                    results["errors"].append({
                        "track_id": track_id,
                        "file_path": str(file_path),
                        "error": "Failed to update file metadata"
                    })
                    continue
                
                # Update database
                LibraryManager.update_track_metadata(db, track_id, **update_kwargs)
                results["successful"] += 1
            
            except Exception as e:
                results["failed"] += 1
                results["errors"].append({
                    "track_id": track_id,
                    "error": str(e)
                })
                logger.error(f"Error in batch update for track {track_id}: {e}")
        
        return results
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in batch update: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@library_router.post("/tracks/{track_id}/artwork")
async def upload_artwork(
    track_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db)
):
    """Upload cover art for a track."""
    try:
        track = LibraryManager.get_track_by_id(db, track_id)
        if not track:
            raise HTTPException(status_code=404, detail="Track not found")
        
        file_path = Path(track.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Track file not found")
        
        # Validate image type
        if not file.content_type or not file.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Read image data
        image_data = await file.read()
        
        # Embed artwork
        success = metadata_processor.embed_artwork_safe(
            file_path,
            image_data,
            file.content_type
        )
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to embed artwork")
        
        # Update database flag
        track.has_artwork = 1
        track.updated_at = datetime.utcnow()
        db.commit()
        
        return {
            "success": True,
            "message": "Artwork uploaded successfully"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error uploading artwork for track {track_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@library_router.get("/tracks/{track_id}/artwork")
async def get_track_artwork(track_id: int, db: Session = Depends(get_db)):
    """Get cover art for a track."""
    try:
        from fastapi.responses import Response
        
        track = LibraryManager.get_track_by_id(db, track_id)
        if not track or not track.has_artwork:
            raise HTTPException(status_code=404, detail="Artwork not found")
        
        file_path = Path(track.file_path)
        if not file_path.exists():
            raise HTTPException(status_code=404, detail="Track file not found")
        
        # Extract artwork from file
        artwork_data = metadata_processor.extract_artwork(file_path, Path("/tmp/temp_artwork"))
        
        if not artwork_data:
            raise HTTPException(status_code=404, detail="No artwork in file")
        
        # Read extracted artwork
        temp_path = Path("/tmp/temp_artwork")
        if not temp_path.exists():
            raise HTTPException(status_code=404, detail="Failed to extract artwork")
        
        with open(temp_path, 'rb') as f:
            image_data = f.read()
        
        # Cleanup temp file
        temp_path.unlink()
        
        # Determine content type
        content_type = "image/jpeg"
        if image_data[:4] == b'\x89PNG':
            content_type = "image/png"
        
        return Response(content=image_data, media_type=content_type)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting artwork for track {track_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Library maintenance endpoints
@library_router.post("/rescan")
async def rescan_library(force: bool = False):
    """Trigger library rescan. Set force=True to re-index all files."""
    try:
        if library_scanner.is_scanning:
            raise HTTPException(status_code=409, detail="Scan already in progress")
        
        success = library_scanner.start_scan(force_full=force)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to start scan")
        
        return {
            "success": True,
            "message": "Library scan started" + (" (full)" if force else "")
        }
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting library rescan: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@library_router.get("/rescan/status")
async def get_rescan_status():
    """Get library rescan status."""
    try:
        return library_scanner.get_status()
    except Exception as e:
        logger.error(f"Error getting rescan status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@library_router.get("/stats")
async def get_library_stats(db: Session = Depends(get_db)):
    """Get library statistics."""
    try:
        total_tracks = LibraryManager.get_total_track_count(db)
        artists = LibraryManager.get_all_artists(db)
        albums = LibraryManager.get_all_albums(db)
        genres = LibraryManager.get_all_genres(db)
        
        return {
            "total_tracks": total_tracks,
            "total_artists": len(artists),
            "total_albums": len(albums),
            "total_genres": len(genres)
        }
    except Exception as e:
        logger.error(f"Error getting library stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Import datetime for artwork endpoint
from datetime import datetime
