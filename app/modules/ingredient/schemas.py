# app/modules/heroes/schemas.py
#
# Schemas Pydantic de entrada y salida para el módulo heroes.
# Separados del modelo de tabla para respetar el principio de
# responsabilidad única: models.py define la DB, schemas.py define
# los contratos HTTP.
from typing import Optional, List
from sqlmodel import SQLModel, Field
from datetime import datetime


class IngredientBase(SQLModel):
    name: str = Field(min_length=2, max_length=100)
    description: Optional[str] = None
    stock_quantity: int = Field(default=0, ge=0)
    is_allergen: bool


# ── Entrada ───────────────────────────────────────────────────────────────────


class IngredientCreate(IngredientBase):
    pass


class IngredientUpdate(SQLModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=100)
    description: Optional[str] = None
    stock_quantity: Optional[int] = Field(default=None, ge=0)
    is_allergen: Optional[bool] = None


# ── Salida ────────────────────────────────────────────────────────────────────


class IngredientPublic(IngredientBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None


class IngredientList(SQLModel):
    data: List[IngredientPublic]
    total: int
