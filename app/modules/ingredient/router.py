# app/modules/ingredientes/router.py
from app.core.deps import require_role
from app.modules.user.models import User
from sqlalchemy.sql.annotation import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from app.core.database import get_session
from app.modules.ingredient.schemas import (
    IngredientCreate,
    IngredientPublic,
    IngredientUpdate,
    IngredientList,
)
from app.modules.ingredient.service import IngredientService

router = APIRouter()


def get_ingredient_service(
    session: Session = Depends(get_session),
) -> IngredientService:
    """Factory de dependencia: inyecta el servicio con su Session."""
    return IngredientService(session)


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/crear",
    response_model=IngredientPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un ingrediente",
)
def create_ingredient(
    data: IngredientCreate,
    _admin: Annotated[User, Depends(require_role(["ADMIN"]))],
    svc: IngredientService = Depends(get_ingredient_service),
) -> IngredientPublic:
    """Router delega al servicio — sin lógica de negocio aquí."""
    return svc.create(data)


@router.get(
    "/",
    response_model=IngredientList,
    summary="Listar ingredientes",
)
def list_ingredientes(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    svc: IngredientService = Depends(get_ingredient_service),
) -> IngredientList:
    return svc.get_all(offset=offset, limit=limit)


@router.get(
    "/{ingredient_id}",
    response_model=IngredientPublic,
    summary="Obtener ingrediente por ID",
)
def get_ingredient(
    ingredient_id: int,
    svc: IngredientService = Depends(get_ingredient_service),
) -> IngredientPublic:
    return svc.get_by_id(ingredient_id)


@router.patch(
    "/actualizar/{ingredient_id}",
    response_model=IngredientPublic,
    summary="Actualización parcial de ingrediente",
)
def update_ingredient(
    ingredient_id: int,
    data: IngredientUpdate,
    _roles  : Annotated[User, Depends(require_role(["ADMIN","STOCK"]))],
    svc: IngredientService = Depends(get_ingredient_service),
) -> IngredientPublic:
    return svc.update(ingredient_id, data)


@router.post(
    "/activate/{ingredient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft activate de ingrediente",
)
def activate_ingredient(
    ingredient_id: int,
    _admin: Annotated[User, Depends(require_role(["ADMIN"]))],
    svc: IngredientService = Depends(get_ingredient_service),
) -> None:
    svc.soft_activate(ingredient_id)


@router.delete(
    "/borrar/{ingredient_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete de ingrediente",
)
def delete_ingredient(
    ingredient_id: int,
    _admin: Annotated[User, Depends(require_role(["ADMIN"]))],
    svc: IngredientService = Depends(get_ingredient_service),
) -> None:
    svc.soft_delete(ingredient_id)
