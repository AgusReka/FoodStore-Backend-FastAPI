from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone

from app.modules.product.models import ProductIngredientLink  # ✅ runtime import

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.product.models import Product


class Ingredient(SQLModel, table=True):
    __tablename__ = "ingredient"

    # PK
    id: Optional[int] = Field(default=None, primary_key=True)
    # Atributos
    name: str = Field(max_length=100, nullable=False, index=True)
    description: Optional[str] = None
    is_allergen: bool = Field(default=True)
    is_active: bool = Field(default=True)

    # Audit
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: Optional[datetime] = Field(default=None)

    # Relaciones (opcional pero útil)
    products: List["Product"] = Relationship(
        back_populates="ingredients", link_model=ProductIngredientLink
    )
