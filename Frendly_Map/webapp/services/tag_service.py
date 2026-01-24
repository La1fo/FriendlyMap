# webapp/services/tag_service.py
from sqlalchemy.orm import Session
from webapp.models.tag import Tag
from typing import List, Dict

class TagService:
    def __init__(self, db: Session):
        self.db = db

    def get_all_tags(self) -> List[Dict]:
        tags = self.db.query(Tag).all()
        return [{"id": t.id, "name": t.name, "category": t.category} for t in tags]
