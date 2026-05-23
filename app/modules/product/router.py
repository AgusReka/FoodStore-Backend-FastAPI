# app/modules/productes/router.py
from app.core.deps import require_admin, require_admin_or_stock
from app.modules.user.models import User
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from app.core.database import get_session
from app.modules.product.schemas import (
    ProductCreate,
    ProductPublic,
    ProductUpdate,
    ProductList,
)
from app.modules.product.service import ProductService

router = APIRouter()


def get_product_service(session: Session = Depends(get_session)) -> ProductService:
    """Factory de dependencia: inyecta el servicio con su Session."""
    return ProductService(session)


# ── Endpoints ─────────────────────────────────────────────────────────────────


@router.post(
    "/",
    response_model=ProductPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Crear un producto",
)
def create_product(
    data: ProductCreate,
    _: Annotated[User, Depends(require_admin)],
    svc: ProductService = Depends(get_product_service),
) -> ProductPublic:
    return svc.create(data)


@router.patch(
    "/{product_id}",
    response_model=ProductPublic,
    summary="Actualización parcial de producto",
)
def update(
    product_id: int,
    data: ProductUpdate,
    _: Annotated[User, Depends(require_admin_or_stock)],
    svc: ProductService = Depends(get_product_service),
) -> ProductPublic:
    return svc.update(product_id, data)


@router.get(
    "/",
    response_model=ProductList,
    summary="Listar productos",
)
def list_productes(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    svc: ProductService = Depends(get_product_service),
) -> ProductList:
    return svc.get_all(offset=offset, limit=limit)


@router.get(
    "/{product_id}",
    response_model=ProductPublic,
    summary="Obtener producto por ID",
)
def get_product(
    product_id: int,
    svc: ProductService = Depends(get_product_service),
) -> ProductPublic:
    return svc.get_by_id(product_id)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft delete de producto",
)
def delete_product(
    product_id: int,
    _: Annotated[User, Depends(require_admin)],
    svc: ProductService = Depends(get_product_service),
) -> None:
    svc.soft_delete(product_id)


@router.post(
    "/{product_id}/activate",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft activate de producto",
)
def activate_product(
    product_id: int,
    _: Annotated[User, Depends(require_admin_or_stock)],
    svc: ProductService = Depends(get_product_service),
) -> None:
    svc.soft_activate(product_id)
