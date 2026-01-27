# webapp/api/map.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from bot.database import get_db_session
from bot.models.location import Location
from bot.models.photo import Photo
from bot.models.location_tag import LocationTag
from bot.models.tag import Tag

router = APIRouter()

@router.get("/locations/approved")
async def get_approved_locations(db: Session = Depends(get_db_session)):
    """
    Возвращает список всех одобренных локаций с фото и тегами.
    """
    locations = db.query(Location).filter(Location.status == "approved", Location.is_deleted.is_(False)).all()
    result = []

    for loc in locations:
        # Получаем теги
        tag_links = db.query(LocationTag).filter(LocationTag.location_id == loc.id).all()
        tags = []
        for link in tag_links:
            tag = db.get(Tag, link.tag_id)
            if tag:
                tags.append(tag.name)

        # Получаем фото
        photos = db.query(Photo).filter(Photo.location_id == loc.id).order_by(Photo.order_index).all()
        photo_list = [{"file_id": p.file_id} for p in photos]

        result.append({
            "id": loc.id,
            "name": loc.name,
            "description": loc.description,
            "latitude": float(loc.latitude),
            "longitude": float(loc.longitude),
            "address": loc.address,
            "created_at": loc.created_at.isoformat(),
            "tags": [{"name": t} for t in tags],
            "photos": photo_list
        })

    return result
