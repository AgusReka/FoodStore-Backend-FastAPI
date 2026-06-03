from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List, TYPE_CHECKING
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, Numeric, Enum as SQLEnum, UniqueConstraint
from app.modules.pedidos.schemas import EstadoPedidoEnum

if TYPE_CHECKING:
    from app.modules.direcciones.models import DireccionEntrega
    from app.modules.pagos.models import FormaPago


class EstadoPedido(SQLModel, table=True):
    __tablename__ = "estado_pedido"

    id: Optional[int] = Field(default=None, primary_key=True)
    codigo: EstadoPedidoEnum = Field(
        sa_column=Column(
            SQLEnum(EstadoPedidoEnum, name="estado_pedido_codigo"),
            unique=True,
            nullable=False,
        )
    )
    descripcion: str = Field(max_length=200)
    orden: int = Field(description="Orden para definir secuencia de estados")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    pedidos: List["Pedido"] = Relationship(back_populates="estado_actual")
    historial_estados: List["HistorialEstadoPedido"] = Relationship(
        back_populates="estado"
    )
    transiciones_salientes: List["TransicionEstado"] = Relationship(
        sa_relationship_kwargs={"foreign_keys": "TransicionEstado.estado_origen_id"}
    )


class TransicionEstado(SQLModel, table=True):
    """Regla persistida: el rol `rol_code` puede mover un pedido de un estado a otro."""

    __tablename__ = "transicion_estado"
    __table_args__ = (
        UniqueConstraint(
            "estado_origen_id",
            "estado_destino_id",
            "rol_code",
            name="uq_transicion_origen_destino_rol",
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    estado_origen_id: int = Field(foreign_key="estado_pedido.id", nullable=False)
    estado_destino_id: int = Field(foreign_key="estado_pedido.id", nullable=False)
    rol_code: str = Field(foreign_key="roles.code", nullable=False, max_length=20)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Pedido(SQLModel, table=True):
    __tablename__ = "pedido"

    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(nullable=False)
    direccion_entrega_id: int = Field(foreign_key="direccion.id", nullable=False)
    forma_pago_id: int = Field(foreign_key="forma_pago.id", nullable=False)
    estado_id: Optional[int] = Field(
        default=1,
        foreign_key="estado_pedido.id",
        nullable=False,
    )
    subtotal: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
    )
    costo_envio: Decimal = Field(
        sa_column=Column(Numeric(10, 2), default=0),
    )
    total: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
    )
    notas_cliente: Optional[str] = Field(max_length=200, default=None)
    # fecha_entrega_estimada: Optional[datetime] = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: Optional[datetime] = Field(default=None)

    @property
    def estado_codigo(self) -> Optional[EstadoPedidoEnum]:
        return self.estado_actual.codigo if self.estado_actual else None

    detalles: List["DetallePedido"] = Relationship(back_populates="pedido")
    historial_estados: List["HistorialEstadoPedido"] = Relationship(
        back_populates="pedido"
    )
    estado_actual: Optional["EstadoPedido"] = Relationship(back_populates="pedidos")
    direccion: Optional["DireccionEntrega"] = Relationship(back_populates="pedidos")
    forma_pago_actual: Optional["FormaPago"] = Relationship(back_populates="pedidos")


class DetallePedido(SQLModel, table=True):
    __tablename__ = "detalle_pedido"

    id: Optional[int] = Field(default=None, primary_key=True)
    pedido_id: int = Field(foreign_key="pedido.id", nullable=False)
    producto_id: int = Field(foreign_key="product.id", nullable=False)

    producto_nombre: str = Field(max_length=200, nullable=False)
    producto_precio_unitario: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
    )
    cantidad: int = Field(nullable=False, ge=1)
    subtotal: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: Optional[datetime] = Field(default=None)

    pedido: Optional["Pedido"] = Relationship(back_populates="detalles")


class HistorialEstadoPedido(SQLModel, table=True):
    __tablename__ = "historial_estado_pedido"

    id: Optional[int] = Field(default=None, primary_key=True)
    pedido_id: int = Field(foreign_key="pedido.id", nullable=False)
    estado_id: int = Field(foreign_key="estado_pedido.id", nullable=False)
    usuario_cambio_id: Optional[int] = Field(default=None, nullable=True)
    observaciones: Optional[str] = Field(max_length=200, default=None)
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), nullable=False
    )

    pedido: Optional["Pedido"] = Relationship(back_populates="historial_estados")
    estado: Optional["EstadoPedido"] = Relationship(back_populates="historial_estados")

    @property
    def fecha_cambio(self) -> datetime:
        return self.created_at

    @property
    def estado_codigo(self) -> Optional[str]:
        return self.estado.codigo.value if self.estado else None
