# app/modules/heroes/schemas.py
#
# Schemas Pydantic de entrada y salida para el módulo heroes.
# Separados del modelo de tabla para respetar el principio de
# responsabilidad única: models.py define la DB, schemas.py define
# los contratos HTTP.
from typing import Optional, List
from sqlmodel import SQLModel, Field
from datetime import datetime


class CategoryBase(SQLModel):
    parent_id: Optional[int] = None
    name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = None
    order_display: int
    image_url: Optional[str] = None


# ── Entrada ───────────────────────────────────────────────────────────────────


class CategoryCreate(CategoryBase):
    pass


class CategoryUpdate(SQLModel):
    parent_id: Optional[int] = None
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = None
    order_display: Optional[int] = None
    image_url: Optional[str] = None


# ── Salida ────────────────────────────────────────────────────────────────────


class CategoryPublic(CategoryBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class CategoryList(SQLModel):
    data: List[CategoryPublic]
    total: int
