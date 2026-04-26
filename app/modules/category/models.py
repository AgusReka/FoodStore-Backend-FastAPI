from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone

from app.modules.product.models import ProductCategoryLink  # ✅ runtime import

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.product.models import Product


class Category(SQLModel, table=True):
    __tablename__ = "category"

    # PK
    id: Optional[int] = Field(default=None, primary_key=True)

    # FK (self reference)
    parent_id: Optional[int] = Field(default=None, foreign_key="category.id")

    # Atributos
    name: str = Field(max_length=100, nullable=False, index=True)
    description: Optional[str] = None
    image_url: Optional[str] = None
    order_display: int = Field(nullable=False)
    is_active: bool = Field(default=True)

    # Audit
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: Optional[datetime] = Field(default=None)

    # Relaciones (opcional pero útil)
    products: List["Product"] = Relationship(
        back_populates="categories", link_model=ProductCategoryLink
    )
