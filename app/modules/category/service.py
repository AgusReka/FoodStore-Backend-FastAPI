# app/modules/category/service.py
from fastapi import HTTPException, status
from sqlmodel import Session

from app.modules.category.models import Category
from app.modules.category.schemas import (
    CategoryCreate,
    CategoryPublic,
    CategoryUpdate,
    CategoryList,
)
from app.modules.category.unit_of_work import CategoryUnitOfWork
from datetime import datetime, timezone


class CategoryService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Helpers privados ──────────────────────────────────────────────────────

    def _get_or_404(self, uow: CategoryUnitOfWork, category_id: int) -> Category:
        category = uow.category.get_by_id(category_id)
        if not category:
            raise ValueError(f"Category con id={category_id} no encontrado")
        return category

    def _assert_name_unique(self, uow: CategoryUnitOfWork, name: str) -> None:
        if uow.category.get_by_name(name):
            raise ValueError(f"El name '{name}' ya está en uso")

    # ── Casos de uso ─────────────────────────────────────────────────────────

    def create(self, data: CategoryCreate) -> CategoryPublic:
        with CategoryUnitOfWork(self._session) as uow:
            self._assert_name_unique(uow, data.name)
            if data.parent_id is not None:
                self._get_or_404(uow, data.parent_id)
            category = Category.model_validate(data)

            uow.category.add(category)

            # Serializar dentro del contexto asegura acceso a atributos lazy
            result = CategoryPublic.model_validate(category)

        return result

    def get_all(
        self,
        offset: int = 0,
        limit: int = 20,
        name: str | None = None,
    ) -> CategoryList:
        with CategoryUnitOfWork(self._session) as uow:
            categories = uow.category.get_all(offset, limit, name=name)
            total = uow.category.count(name=name)
            result = CategoryList(
                data=[CategoryPublic.model_validate(h) for h in categories],
                total=total,
            )

        return result

    def get_by_id(self, category_id: int) -> CategoryPublic:
        with CategoryUnitOfWork(self._session) as uow:
            category = self._get_or_404(uow, category_id)
            result = CategoryPublic.model_validate(category)

        return result

    def update(self, category_id: int, data: CategoryUpdate) -> CategoryPublic:
        with CategoryUnitOfWork(self._session) as uow:
            category = self._get_or_404(uow, category_id)

            if data.name and data.name != category.name:
                self._assert_name_unique(uow, data.name)

            if data.parent_id is not None:
                self._get_or_404(uow, data.parent_id)
            # Solo campos enviados por el cliente
            patch = data.model_dump(exclude_unset=True)

            for field, value in patch.items():
                setattr(category, field, value)
            category.updated_at = datetime.now(timezone.utc)
            result = CategoryPublic.model_validate(category)

        return result

    def soft_delete(self, category_id: int) -> None:
        with CategoryUnitOfWork(self._session) as uow:
            category = self._get_or_404(uow, category_id)
            category.is_active = False
            category.deleted_at = datetime.now(timezone.utc)

    def soft_activate(self, category_id: int) -> None:
        with CategoryUnitOfWork(self._session) as uow:
            category = self._get_or_404(uow, category_id)
            category.is_active = True
            category.deleted_at = None
