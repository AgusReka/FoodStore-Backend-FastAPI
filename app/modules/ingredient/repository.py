# app/modules/Ingredients/repository.py
from sqlmodel import Session, select
from app.core.repository import BaseRepository
from app.modules.ingredient.models import Ingredient


class IngredientRepository(BaseRepository[Ingredient]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Ingredient)

    def get_by_name(self, name: str) -> Ingredient | None:
        return self.session.exec(
            select(Ingredient).where(Ingredient.name == name)
        ).first()

    def get_all(self, offset=0, limit=20):
        return list(
            self.session.exec(select(Ingredient).offset(offset).limit(limit)).all()
        )

    def get_all_in(self, ids: list[int]) -> list[Ingredient]:
        return list(
            self.session.exec(select(Ingredient).where(Ingredient.id.in_(ids))).all()
        )

    def count(self) -> int:
        return len(self.session.exec(select(Ingredient)).all())
