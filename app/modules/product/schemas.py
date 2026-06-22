from sqlmodel import SQLModel, Field
from typing import Optional, List
from decimal import Decimal
from datetime import datetime


class ProductCategoryInput(SQLModel):
    id: int
    is_primary: bool


class ProductCategoryPublic(SQLModel):
    id: int
    name: str
    is_primary: bool


class ProductIngredientInput(SQLModel):
    id: int
    is_removable: bool
    quantity: int = Field(default=1, ge=1)


class ProductIngredientPublic(SQLModel):
    id: int
    name: str
    is_removable: bool
    quantity: int
    is_allergen: bool
    has_stock: bool


class ProductBase(SQLModel):
    name: str = Field(min_length=2, max_length=150)
    description: Optional[str] = None
    stock_quantity: int = Field(default=0)
    base_price: Decimal = Field(ge=0)

    image_urls: List[str] = Field(default_factory=list)

    prep_time_min: Optional[int] = Field(default=None, ge=0)

    available: bool = True


class ProductCreate(ProductBase):
    categories: list[ProductCategoryInput] = Field(default_factory=list)
    ingredients: list[ProductIngredientInput] = Field(default_factory=list)
    pass


class ProductUpdate(SQLModel):
    name: Optional[str] = Field(default=None, min_length=2, max_length=150)
    description: Optional[str] = None

    base_price: Optional[Decimal] = Field(default=None, ge=0)
    stock_quantity: Optional[int] = Field(default=None, ge=0)
    image_urls: Optional[List[str]] = None

    prep_time_min: Optional[int] = Field(default=None, ge=0)

    available: Optional[bool] = None

    # ⚠️ importante: None = no tocar, [] = vaciar (pero vos no lo permitís)
    categories: Optional[list[ProductCategoryInput]] = None
    ingredients: list[ProductIngredientInput] = None


class ProductPublic(ProductBase):
    id: int

    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    categories: list[ProductCategoryPublic] = Field(default_factory=list)
    ingredients: list[ProductIngredientPublic] = Field(default_factory=list)

    # Stock calculado en vivo: para productos con receta es el mínimo de
    # (ingrediente.stock_quantity / cantidad_necesaria); para standalone
    # es simplemente stock_quantity.
    available_stock: int = 0


class ProductList(SQLModel):
    total: int
    data: list[ProductPublic]


class ProductAvailabilityUpdate(SQLModel):
    available: bool


class IngredientShortage(SQLModel):
    ingredient_id: int
    ingredient_name: str
    required: int
    available: int
    missing: int


class ProductStockShortagePublic(SQLModel):
    product_id: int
    available_stock: int
    shortages: list[IngredientShortage]
