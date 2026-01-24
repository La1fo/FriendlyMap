# webapp/api/tag.py
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from bot.database import get_db_session
from bot.models.tag import Tag

router = APIRouter()

@router.get("/tags")
async def get_tags(db: Session = Depends(get_db_session)):
    """Возвращает все теги для фильтрации на карте"""
    tags = db.query(Tag).all()
    return [{"id": t.id, "name": t.name, "category": t.category} for t in tags]
