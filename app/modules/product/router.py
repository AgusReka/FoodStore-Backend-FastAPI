# app/modules/productes/router.py
from app.core.deps import require_admin, require_admin_or_stock
from app.modules.user.models import User
from decimal import Decimal
from typing import Annotated
from fastapi import APIRouter, Depends, Query, status
from sqlmodel import Session

from app.core.database import get_session
from app.modules.product.schemas import (
    ProductCreate,
    ProductPublic,
    ProductUpdate,
    ProductList,
    ProductAvailabilityUpdate,
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
    include_deleted: bool = Query(default=False),
    name: str | None = Query(default=None, description="Substring case-insensitive"),
    category_id: int | None = Query(default=None),
    cascade: bool = Query(default=True, description="Si true, incluye productos de subcategorías"),
    price_min: Decimal | None = Query(default=None, ge=0),
    price_max: Decimal | None = Query(default=None, ge=0),
    ingredient_ids: list[int] | None = Query(default=None, description="AND: el producto debe contener TODOS"),
    available: bool | None = Query(default=None),
    svc: ProductService = Depends(get_product_service),
) -> ProductList:
    return svc.get_all(
        offset=offset,
        limit=limit,
        include_deleted=include_deleted,
        name=name,
        category_id=category_id,
        cascade=cascade,
        price_min=price_min,
        price_max=price_max,
        ingredient_ids=ingredient_ids,
        available=available,
    )


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


@router.patch(
    "/{product_id}/availability",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Pausar/reanudar venta del producto",
)
def set_product_availability(
    product_id: int,
    data: ProductAvailabilityUpdate,
    _: Annotated[User, Depends(require_admin_or_stock)],
    svc: ProductService = Depends(get_product_service),
) -> None:
    svc.set_availability(product_id, data.available)
