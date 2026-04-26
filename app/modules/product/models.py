from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, Numeric
from sqlalchemy.dialects.postgresql import ARRAY, TEXT

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.category.models import Category
    from app.modules.ingredient.models import Ingredient


class ProductCategoryLink(SQLModel, table=True):
    __tablename__ = "product_category"
    # Composite PK
    product_id: Optional[int] = Field(
        default=None, foreign_key="product.id", primary_key=True
    )
    category_id: Optional[int] = Field(
        default=None, foreign_key="category.id", primary_key=True
    )

    # Attributes
    is_primary: bool = Field(default=False, nullable=False)

    # Audit
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProductIngredientLink(SQLModel, table=True):
    __tablename__ = "product_ingredient"
    # Composite PK
    product_id: Optional[int] = Field(
        default=None, foreign_key="product.id", primary_key=True
    )
    ingredient_id: Optional[int] = Field(
        default=None, foreign_key="ingredient.id", primary_key=True
    )

    # Attributes
    is_removable: bool = Field(default=False, nullable=False)

    # Audit
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Product(SQLModel, table=True):
    __tablename__ = "product"

    # PK
    id: Optional[int] = Field(default=None, primary_key=True)

    # Attributes
    name: str = Field(max_length=150, nullable=False)
    description: Optional[str] = None
    base_price: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))

    image_urls: List[str] = Field(sa_column=Column(ARRAY(TEXT)), default_factory=list)
    stock_quantity: int = 0
    prep_time_min: Optional[int] = None

    available: bool = Field(default=True, nullable=False)

    # Audit
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: Optional[datetime] = Field(default=None)

    # Relationships (N:N)
    categories: List["Category"] = Relationship(
        back_populates="products", link_model=ProductCategoryLink
    )
    ingredients: List["Ingredient"] = Relationship(
        back_populates="products", link_model=ProductIngredientLink
    )
