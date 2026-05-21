from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, Numeric
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.pedidos.models import Pedido

class FormaPago(SQLModel, table=True):
    """
    Formas de pago disponibles (efectivo, tarjeta, etc.)
    Tabla de referencia maestra.
    """
    __tablename__ = "forma_pago"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(max_length=50, nullable=False)
    monto_pago: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False))
    habilitado: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: Optional[datetime] = Field(default=None)
    
    #Relacion 
    pedidos: List["Pedido"] = Relationship(back_populates="forma_pago")