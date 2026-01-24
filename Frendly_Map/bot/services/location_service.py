# bot/services/location_service.py
from sqlalchemy.orm import Session
from bot.models.location import Location
from bot.models.photo import Photo
from bot.models.tag import Tag
from bot.models.location_tag import LocationTag
from datetime import datetime
from bot.models.user import User
class LocationService:

    @staticmethod
    def create_location(db: Session, user_id: int, name: str, latitude: float,
                        longitude: float, description=None, address=None):
        loc = Location(
            user_id=user_id,
            name=name,
            latitude=latitude,
            longitude=longitude,
            description=description,
            address=address,
            status="pending"
        )
        db.add(loc)

        # сразу начисляем очки
        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.points += 5

        db.commit()
        db.refresh(loc)
        return loc


    @staticmethod
    def approve_location(db: Session, location_id: int, moderator_id: int, comment=None):
        loc = db.query(Location).get(location_id)
        if not loc:
            raise ValueError("Локация не найдена")
        loc.status = "approved"
        loc.approved_by = moderator_id
        loc.moderation_comment = comment
        loc.moderated_at = datetime.utcnow()
        db.add(loc)
        db.commit()
        db.refresh(loc)
        return loc

    @staticmethod
    def add_tag(db: Session, location_id: int, tag_name: str, category=None):
        tag = db.query(Tag).filter(Tag.name == tag_name).first()
        if not tag:
            tag = Tag(name=tag_name, category=category)
            db.add(tag)
            db.commit()
            db.refresh(tag)
        link = LocationTag(location_id=location_id, tag_id=tag.id)
        db.add(link)
        db.commit()
        return link

    @staticmethod
    def add_photo(db: Session, location_id: int, file_id: str, description=None, order_index=0):
        photo = Photo(location_id=location_id, file_id=file_id, description=description, order_index=order_index)
        db.add(photo)
        db.commit()
        db.refresh(photo)
        return photo
