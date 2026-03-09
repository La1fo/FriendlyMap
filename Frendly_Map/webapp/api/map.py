import json
from urllib.parse import urlencode
from urllib.request import urlopen

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import Response
from sqlalchemy.orm import Session

from bot.database import get_db_session
from bot.models.location import Location
from bot.models.location_tag import LocationTag
from bot.models.photo import Photo
from bot.models.tag import Tag
from webapp.config import settings

router = APIRouter()


def _load_location_tags(db: Session, location_id: int) -> list[dict]:
    tag_links = db.query(LocationTag).filter(LocationTag.location_id == location_id).all()
    tags = []
    for link in tag_links:
        tag = db.get(Tag, link.tag_id)
        if tag:
            tags.append({"id": tag.id, "name": tag.name, "category": tag.category})
    return tags


def _load_location_photos(db: Session, location_id: int) -> list[dict]:
    photos = db.query(Photo).filter(Photo.location_id == location_id).order_by(Photo.order_index).all()
    return [
        {
            "file_id": photo.file_id,
            "url": f"/api/map/photos?file_id={photo.file_id}",
            "order_index": photo.order_index,
        }
        for photo in photos
    ]


@router.get("/locations/approved")
async def get_approved_locations(db: Session = Depends(get_db_session)):
    locations = db.query(Location).filter(Location.status == "approved").all()
    result = []

    for loc in locations:
        result.append(
            {
                "id": loc.id,
                "name": loc.name,
                "description": loc.description,
                "latitude": float(loc.latitude),
                "longitude": float(loc.longitude),
                "address": loc.address,
                "created_at": loc.created_at.isoformat() if loc.created_at else None,
                "tags": _load_location_tags(db, loc.id),
                "photos": _load_location_photos(db, loc.id),
            }
        )

    return {"items": result, "count": len(result)}


@router.get("/photos")
async def map_photo_proxy(file_id: str = Query(..., min_length=1)):
    if not settings.BOT_TOKEN:
        raise HTTPException(status_code=503, detail="BOT_TOKEN is not configured")

    try:
        get_file_url = f"https://api.telegram.org/bot{settings.BOT_TOKEN}/getFile?{urlencode({'file_id': file_id})}"
        with urlopen(get_file_url, timeout=8) as res:
            payload = json.loads(res.read().decode("utf-8"))

        if not payload.get("ok"):
            raise HTTPException(status_code=404, detail="Photo not found in Telegram")

        file_path = payload["result"]["file_path"]
        download_url = f"https://api.telegram.org/file/bot{settings.BOT_TOKEN}/{file_path}"
        with urlopen(download_url, timeout=12) as file_res:
            content = file_res.read()
            content_type = file_res.headers.get_content_type() or "image/jpeg"

        return Response(content=content, media_type=content_type)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=502, detail="Unable to load photo")


@router.get("/route")
async def build_route(
    start_lat: float,
    start_lng: float,
    end_lat: float,
    end_lng: float,
):
    coords = f"{start_lng},{start_lat};{end_lng},{end_lat}"
    osrm_url = (
        f"{settings.OSRM_BASE_URL.rstrip('/')}/route/v1/driving/{coords}"
        "?overview=full&geometries=geojson"
    )

    try:
        with urlopen(osrm_url, timeout=10) as res:
            payload = json.loads(res.read().decode("utf-8"))
    except Exception:
        raise HTTPException(status_code=502, detail="Routing service unavailable")

    routes = payload.get("routes") or []
    if not routes:
        raise HTTPException(status_code=404, detail="Route not found")

    route = routes[0]
    geometry = route.get("geometry", {}).get("coordinates", [])
    points = [{"lat": lat, "lng": lng} for lng, lat in geometry]

    return {
        "distance_m": route.get("distance", 0),
        "duration_s": route.get("duration", 0),
        "points": points,
    }
