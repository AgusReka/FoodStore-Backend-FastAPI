# app/modules/categoryes/router.py
from app.core.deps import require_role
from app.modules.user.models import User
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from app.core.database import get_session
from app.modules.category.schemas import (
    CategoryCreate,
    CategoryPublic,
    CategoryUpdate,
    CategoryList,
)
from app.modules.category.service import CategoryService

router = APIRouter()


def get_category_service(session: Session = Depends(get_session)) -> CategoryService:
    """Factory de dependencia: inyecta el servicio con su Session."""
    return CategoryService(session)


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/",
    response_model=CategoryPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Crear una categoria",
)
def create_category(
    data: CategoryCreate,
    _admin: Annotated[User, Depends(require_role(["ADMIN"]))],
    svc: CategoryService = Depends(get_category_service),
) -> CategoryPublic:
    return svc.create(data)


@router.get(
    "/",
    response_model=CategoryList,
    summary="Listar categorias",
)
def list_categoryes(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    svc: CategoryService = Depends(get_category_service),
) -> CategoryList:
    return svc.get_all(offset=offset, limit=limit)


@router.get(
    "/{category_id}",
    response_model=CategoryPublic,
    summary="Obtener categoria por ID",
)
def get_category(
    category_id: int,
    svc: CategoryService = Depends(get_category_service),
) -> CategoryPublic:
    return svc.get_by_id(category_id)


@router.patch(
    "/{category_id}",
    response_model=CategoryPublic,
    summary="Actualización parcial de categoria",
)
def update_category(
    category_id: int,
    data: CategoryUpdate,
    _admin: Annotated[User, Depends(require_role(["ADMIN"]))],
    svc: CategoryService = Depends(get_category_service),
) -> CategoryPublic:
    return svc.update(category_id, data)


@router.post(
    "/{category_id}/activate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft activate de categoria",
)
def activate_category(
    category_id: int,
    _admin: Annotated[User, Depends(require_role(["ADMIN"]))],
    svc: CategoryService = Depends(get_category_service),
) -> None:
    svc.soft_activate(category_id)


@router.delete(
    "/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete de categoria",
)
def delete_category(
    category_id: int,
    _admin: Annotated[User, Depends(require_role(["ADMIN"]))],
    svc: CategoryService = Depends(get_category_service),
) -> None:
    svc.soft_delete(category_id)
