# app/modules/Categoryes/repository.py
from sqlmodel import Session, select
from app.core.repository import BaseRepository
from app.modules.category.models import Category


class CategoryRepository(BaseRepository[Category]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Category)

    def get_by_name(self, name: str) -> Category | None:
        return self.session.exec(select(Category).where(Category.name == name)).first()

    def get_all(self, offset=0, limit=20):
        return list(
            self.session.exec(select(Category).offset(offset).limit(limit)).all()
        )

    def get_all_in(self, ids: list[int]) -> list[Category]:
        return list(
            self.session.exec(select(Category).where(Category.id.in_(ids))).all()
        )

    def count(self) -> int:
        return len(self.session.exec(select(Category)).all())
