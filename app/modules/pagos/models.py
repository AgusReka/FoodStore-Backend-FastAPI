from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from decimal import Decimal
from sqlalchemy import Column, BigInteger, Numeric

if TYPE_CHECKING:
    from app.modules.pedidos.models import Pedido


class FormaPago(SQLModel, table=True):
    __tablename__ = "forma_pago"

    id: Optional[int] = Field(default=None, primary_key=True)
    nombre: str = Field(max_length=50, nullable=False)
    descripcion: Optional[str] = Field(default=None, max_length=200)
    requiere_monto_pago: bool = Field(default=False)
    is_active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: Optional[datetime] = Field(default=None)

    pedidos: List["Pedido"] = Relationship(back_populates="forma_pago_actual")


class PagoMP(SQLModel, table=True):
    __tablename__ = "pagos_mp"

    id: Optional[int] = Field(default=None, primary_key=True)
    pedido_id: int = Field(foreign_key="pedido.id", nullable=False)
    mp_payment_id: Optional[int] = Field(
        default=None,
        sa_column=Column(BigInteger, unique=True, nullable=True)
    )
    mp_status: str = Field(max_length=30, nullable=False)
    mp_status_detail: Optional[str] = Field(default=None, max_length=100)
    transaction_amount: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False)
    )
    external_reference: str = Field(max_length=100, unique=True, nullable=False)
    idempotency_key: str = Field(max_length=100, unique=True, nullable=False)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    pedido: Optional["Pedido"] = Relationship()
