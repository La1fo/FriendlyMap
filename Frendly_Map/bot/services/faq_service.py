from sqlalchemy.orm import Session

from bot.models.faq_item import FaqItem


class FaqService:
    @staticmethod
    def list_items(db: Session):
        return db.query(FaqItem).order_by(FaqItem.id.asc()).all()

    @staticmethod
    def get_item(db: Session, item_id: int):
        return db.get(FaqItem, item_id)

    @staticmethod
    def create_item(db: Session, question: str, answer: str, created_by: int) -> FaqItem:
        item = FaqItem(question=question.strip(), answer=answer.strip(), created_by=created_by)
        db.add(item)
        db.commit()
        db.refresh(item)
        return item

    @staticmethod
    def delete_item(db: Session, item: FaqItem) -> None:
        db.delete(item)
        db.commit()
