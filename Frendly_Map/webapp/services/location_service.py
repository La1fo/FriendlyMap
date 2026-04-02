# webapp/services/location_service.py
from sqlalchemy.orm import Session
from shared.models.location import Location
from shared.models.photo import Photo
from shared.models.tag import Tag
from shared.models.location_tag import LocationTag
from typing import List, Dict

class LocationService:
    def __init__(self, db: Session):
        self.db = db

    def get_approved_locations(self) -> List[Dict]:
        """Возвращает список одобренных локаций с фото и тегами"""
        locations = self.db.query(Location).filter(Location.status == "approved").all()
        result = []

        for loc in locations:
            # Получаем теги
            tag_ids = [lt.tag_id for lt in loc.tags]
            tags = self.db.query(Tag).filter(Tag.id.in_(tag_ids)).all() if tag_ids else []

            # Фото
            photos = [{"file_id": p.file_id, "description": p.description} for p in loc.photos]

            result.append({
                "id": loc.id,
                "name": loc.name,
                "description": loc.description,
                "latitude": float(loc.latitude),
                "longitude": float(loc.longitude),
                "address": loc.address,
                "created_at": loc.created_at.isoformat(),
                "tags": [{"id": t.id, "name": t.name} for t in tags],
                "photos": photos
            })
        return result

    def get_location_by_id(self, location_id: int) -> Dict | None:
        """Возвращает конкретную локацию с фото и тегами"""
        loc = self.db.query(Location).filter(Location.id == location_id, Location.status=="approved").first()
        if not loc:
            return None

        tag_ids = [lt.tag_id for lt in loc.tags]
        tags = self.db.query(Tag).filter(Tag.id.in_(tag_ids)).all() if tag_ids else []

        photos = [{"file_id": p.file_id, "description": p.description} for p in loc.photos]

        return {
            "id": loc.id,
            "name": loc.name,
            "description": loc.description,
            "latitude": float(loc.latitude),
            "longitude": float(loc.longitude),
            "address": loc.address,
            "created_at": loc.created_at.isoformat(),
            "tags": [{"id": t.id, "name": t.name} for t in tags],
            "photos": photos
        }
