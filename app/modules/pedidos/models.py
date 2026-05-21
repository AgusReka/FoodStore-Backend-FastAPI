from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone
from enum import Enum
from decimal import Decimal
from sqlalchemy import Column, Numeric, Enum as SQLEnum
import enum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.direcciones.models import DireccionEntrega
    from app.modules.pagos.models import FormaPago

#Enum para estado del pedido
class EstadoPedidoEnum(str, Enum):
    PENDIENTE = "PENDIENTE"
    CONFIRMADO = "CONFIRMADO"
    EN_PREP = "EN_PREP"  
    EN_CAMINO = "EN_CAMINO"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"
    
# MODELOS PRINCIPALES
class EstadoPedido(SQLModel, table = True):
    """
    Tabla de estados posibles del pedido.
    Se usa para validar transiciones
    """
    __tablename__ = "estado_pedido"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    codigo: EstadoPedidoEnum = Field(
        sa_column=Column(SQLEnum(EstadoPedidoEnum, name="estado_pedido_codigo"),unique=True, nullable=False))
    descripcion: str = Field(max_length=200)
    orden: int = Field(description="Orden para definir secuencia de estados")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
class Pedido(SQLModel, table=True):
    """
    Pedido principal realizado por un cliente.
    Contiene información general del pedido
    """
    __tablename__ = "pedido"
    id: Optional[int] = Field(default=None, primary_key=True)
    #FK - Cleinte
    usuario_id: int = Field(
        foreign_key="usuario.id", nullable=False)
    #FK - Direccion de entrega
    direccion_entrega_id: int = Field(
        foreign_key="direccion.id", nullable=False)
    #FK - Forma de Pago
    forma_pago_id: int = Field(
        foreign_key="forma_pago.id", nullable=False)
    #FK - Estado del Pedido
    estado_id: Optional[int] = Field(
        default = 1, #ES PENDIENTE POR DEFECTO
        foreign_key = "estado_pedido.id", 
        nullable=False
    )
    # Datos del pedido 
    subtotal: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
        description="Subtotal sin impuestos ni envío"
    )
    costo_envio: Decimal = Field(
        sa_column=Column(Numeric(10, 2), default=0),
        description="Costo de envío"
    )
    total: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
        description="Total final del pedido"
    )
    notas_cliente: Optional[str] = Field(max_length=200, default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: Optional[datetime] = Field(default=None)
    
    #relaciones
    detalles: List["DetallePedido"] = Relationship(back_populates="pedido")
    historial_estados: List["HistorialEstadoPedido"] = Relationship(
        back_populates="pedido"
    )
    estado_actual: Optional["EstadoPedido"] = Relationship(
        back_populates="pedidos"
    )
    direccion: Optional["DireccionEntrega"] = Relationship(
        back_populates="pedidos"
    )
    forma_pago_actual: Optional["FormaPago"] = Relationship(
        back_populates="pedidos"
    )
    
class DetallePedido(SQLModel, table=True):
    """
    Detalle de cada producto en el pedido.
    Guarda precio y nombre inmutables al momento de crear.
    """
    __tablename__ = "detlle_pedido"
    id: Optional[int] = Field(default=None, primary_key=True)
    #FK
    pedido_id: int = Field(foreign_key="pedido.id", nullable=False)
    producto_id: int = Field(foreign_key="producto.id", nullable=False)
    
    #Datos del prducto al momentdo del pedido
    producto_nombre: str = Field(
        max_length = 200,
        nullable=False,
        description="Nombre del producto"
    )
    producto_precio_unitario: Decimal = Field(
        sa_column=Column(Numeric(10, 2), nullable=False),
        description="Precio unitario del producto"
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
    """
    Guarda el historial de cambios de estado del pedido.
    Permite auditar y validar transiciones.
    """
    __tablename__ = "historial_estado_pedido"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    #FK
    pedido_id: int = Field(foreign_key="pedido.id", nullable=False)
    estado_id: int = Field(foreign_key="estado_pedido.id", nullable=False)
    #Tiempo que se ralizo el cambio
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc),
                                   nullable=False)
    observaciones: Optional[str] = Field(max_length=200, default=None)
    
    
    pedido: Optional["Pedido"] = Relationship(back_populates="historial_estados")
    estado: Optional["EstadoPedido"] = Relationship(back_populates="historial_estados")
    