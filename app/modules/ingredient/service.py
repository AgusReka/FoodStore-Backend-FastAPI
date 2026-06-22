# app/modules/ingredient/service.py
from sqlmodel import Session

from app.core.exceptions.custom_exceptions import (
    DuplicateResourceError,
    ResourceNotFoundError,
)

from app.modules.ingredient.models import Ingredient
from app.modules.ingredient.schemas import (
    IngredientCreate,
    IngredientPublic,
    IngredientUpdate,
    IngredientList,
)
from app.modules.ingredient.unit_of_work import IngredientUnitOfWork
from datetime import datetime, timezone


class IngredientService:
    def __init__(self, session: Session) -> None:
        self._session = session

    # ── Helpers privados ──────────────────────────────────────────────────────

    def _get_or_404(self, uow: IngredientUnitOfWork, ingredient_id: int) -> Ingredient:
        ingredient = uow.ingredient.get_by_id(ingredient_id)
        if not ingredient:
            raise ResourceNotFoundError(resource="ingrediente", identifier=ingredient_id)
        return ingredient

    def _assert_name_unique(self, uow: IngredientUnitOfWork, name: str) -> None:
        if uow.ingredient.get_by_name(name):
            raise DuplicateResourceError(resource="ingrediente", field="name", value=name)

    # ── Casos de uso ─────────────────────────────────────────────────────────

    def create(self, data: IngredientCreate) -> IngredientPublic:
        with IngredientUnitOfWork(self._session) as uow:
            self._assert_name_unique(uow, data.name)

            ingredient = Ingredient.model_validate(data)

            uow.ingredient.add(ingredient)

            # Serializar dentro del contexto asegura acceso a atributos lazy
            result = IngredientPublic.model_validate(ingredient)

        return result

    def get_all(
        self,
        offset: int = 0,
        limit: int = 20,
        name: str | None = None,
    ) -> IngredientList:
        with IngredientUnitOfWork(self._session) as uow:
            ingredients = uow.ingredient.get_all(offset, limit, name=name)
            total = uow.ingredient.count(name=name)
            result = IngredientList(
                data=[IngredientPublic.model_validate(h) for h in ingredients],
                total=total,
            )

        return result

    def get_by_id(self, ingredient_id: int) -> IngredientPublic:
        with IngredientUnitOfWork(self._session) as uow:
            ingredient = self._get_or_404(uow, ingredient_id)
            result = IngredientPublic.model_validate(ingredient)

        return result

    def update(self, ingredient_id: int, data: IngredientUpdate) -> IngredientPublic:
        with IngredientUnitOfWork(self._session) as uow:
            ingredient = self._get_or_404(uow, ingredient_id)

            if data.name and data.name != ingredient.name:
                self._assert_name_unique(uow, data.name)

            # Solo campos enviados por el cliente
            patch = data.model_dump(exclude_unset=True)

            for field, value in patch.items():
                setattr(ingredient, field, value)
            ingredient.updated_at = datetime.now(timezone.utc)
            result = IngredientPublic.model_validate(ingredient)

        return result

    def soft_delete(self, ingredient_id: int) -> None:
        with IngredientUnitOfWork(self._session) as uow:
            ingredient = self._get_or_404(uow, ingredient_id)
            ingredient.is_active = False
            ingredient.deleted_at = datetime.now(timezone.utc)

    def soft_activate(self, ingredient_id: int) -> None:
        with IngredientUnitOfWork(self._session) as uow:
            ingredient = self._get_or_404(uow, ingredient_id)
            ingredient.is_active = True
            ingredient.deleted_at = None
