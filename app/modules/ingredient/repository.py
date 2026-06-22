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

    def _apply_filters(self, stmt, name: str | None):
        if name:
            stmt = stmt.where(Ingredient.name.ilike(f"%{name}%"))
        return stmt

    def get_all(self, offset=0, limit=20, name: str | None = None):
        stmt = self._apply_filters(select(Ingredient), name).offset(offset).limit(limit)
        return list(self.session.exec(stmt).all())

    def get_all_in(self, ids: list[int]) -> list[Ingredient]:
        return list(
            self.session.exec(select(Ingredient).where(Ingredient.id.in_(ids))).all()
        )

    def get_all_in_for_update(self, ids: list[int]) -> list[Ingredient]:
        return list(
            self.session.exec(
                select(Ingredient).where(Ingredient.id.in_(ids)).with_for_update()
            ).all()
        )

    def count(self, name: str | None = None) -> int:
        stmt = self._apply_filters(select(Ingredient), name)
        return len(self.session.exec(stmt).all())
