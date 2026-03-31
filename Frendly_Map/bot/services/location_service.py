# bot/services/location_service.py
from datetime import datetime

from sqlalchemy.orm import Session

from bot.models.location import Location
from bot.models.location_tag import LocationTag
from bot.models.photo import Photo
from bot.models.tag import Tag
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

        user = db.query(User).filter(User.id == user_id).first()
        if user:
            user.moderation_locations += 1

        db.commit()
        db.refresh(loc)
        return loc

    @staticmethod
    def approve_location(db: Session, location_id: int, moderator_id: int, comment=None):
        loc = db.get(Location, location_id)
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
    def ensure_tags(db: Session, category_to_tags: dict[str, list[str]]) -> None:
        existing_tags = {(t.name, t.category): t for t in db.query(Tag).all()}
        changed = False

        for category, tags in category_to_tags.items():
            for tag_name in tags:
                if (tag_name, category) in existing_tags:
                    continue
                db.add(Tag(name=tag_name, category=category))
                changed = True

        if changed:
            db.commit()

    @staticmethod
    def add_tag(db: Session, location_id: int, tag_name: str, category=None):
        tag = db.query(Tag).filter(Tag.name == tag_name, Tag.category == category).first()
        if not tag:
            tag = Tag(name=tag_name, category=category)
            db.add(tag)
            db.commit()
            db.refresh(tag)

        existing_link = db.query(LocationTag).filter(
            LocationTag.location_id == location_id,
            LocationTag.tag_id == tag.id,
        ).first()
        if existing_link:
            return existing_link

        link = LocationTag(location_id=location_id, tag_id=tag.id)
        db.add(link)
        db.commit()
        return link

    @staticmethod
    def add_tags_by_ids(db: Session, location_id: int, tag_ids: list[int]) -> None:
        if not tag_ids:
            return

        existing_ids = {
            tag_id for (tag_id,) in db.query(LocationTag.tag_id)
            .filter(LocationTag.location_id == location_id)
            .all()
        }

        changed = False
        for tag_id in set(tag_ids):
            if tag_id in existing_ids:
                continue
            db.add(LocationTag(location_id=location_id, tag_id=tag_id))
            changed = True

        if changed:
            db.commit()

    @staticmethod
    def add_photo(db: Session, location_id: int, file_id: str, description=None, order_index=0):
        photo = Photo(location_id=location_id, file_id=file_id, description=description, order_index=order_index)
        db.add(photo)
        db.commit()
        db.refresh(photo)
        return photo
