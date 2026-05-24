# app/modules/Categoryes/repository.py
from sqlmodel import Session, select
from app.core.repository import BaseRepository
from app.modules.category.models import Category


class CategoryRepository(BaseRepository[Category]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, Category)

    def get_by_name(self, name: str) -> Category | None:
        return self.session.exec(select(Category).where(Category.name == name)).first()

    def _apply_filters(self, stmt, name: str | None):
        if name:
            stmt = stmt.where(Category.name.ilike(f"%{name}%"))
        return stmt

    def get_all(self, offset=0, limit=20, name: str | None = None):
        stmt = self._apply_filters(select(Category), name).offset(offset).limit(limit)
        return list(self.session.exec(stmt).all())

    def get_all_in(self, ids: list[int]) -> list[Category]:
        return list(
            self.session.exec(select(Category).where(Category.id.in_(ids))).all()
        )

    def count(self, name: str | None = None) -> int:
        stmt = self._apply_filters(select(Category), name)
        return len(self.session.exec(stmt).all())

    def get_descendant_ids(self, category_id: int, include_self: bool = True) -> list[int]:
        """
        Devuelve la lista plana de IDs de descendientes del nodo dado (incluyéndolo
        opcionalmente). Implementación iterativa en Python — adecuada para datasets
        chicos (<1k categorías).
        """
        all_cats = self.session.exec(select(Category)).all()
        children_map: dict[int, list[int]] = {}
        for cat in all_cats:
            if cat.parent_id is not None:
                children_map.setdefault(cat.parent_id, []).append(cat.id)

        result: list[int] = [category_id] if include_self else []
        stack: list[int] = [category_id]
        seen: set[int] = {category_id}
        while stack:
            current = stack.pop()
            for child_id in children_map.get(current, []):
                if child_id in seen:
                    continue
                seen.add(child_id)
                result.append(child_id)
                stack.append(child_id)
        return result
