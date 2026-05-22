from typing import Optional, List
from sqlmodel import SQLModel, Field
from datetime import datetime
from decimal import Decimal
from enum import Enum

class EstadoPedidoEnum(str, Enum):
    PENDIENTE = "PENDIENTE"
    CONFIRMADO = "CONFIRMADO"
    EN_PREP = "EN_PREP"
    EN_CAMINO = "EN_CAMINO"
    ENTREGADO = "ENTREGADO"
    CANCELADO = "CANCELADO"
    
class EstadoPedidoBase(SQLModel):
    codigo: EstadoPedidoEnum
    descripcion: str = Field(max_length=200)
    orden: int

class EstadoPedidoCreate(EstadoPedidoBase):
    pass

class EstadoPedidoPublic(EstadoPedidoBase):
    id: int
    created_at: datetime
    
class DetallePedidoBase(SQLModel):
    producto_id: int
    cantidad: int = Field(ge=1, description="Cantidad mínima: 1")

class DetallePedidoCreate(DetallePedidoBase):
    pass

class DetallePedidoPublic(DetallePedidoBase):
    id: int
    pedido_id: int
    producto_nombre: str
    producto_precio_unitario: Decimal
    subtotal: Decimal
    created_at: datetime
    
class PedidoBase(SQLModel):
    direccion_entrega_id: Optional[int] = None
    forma_pago_id: Optional[int] = None
    notas_cliente: Optional[str] = Field(default=None, max_length=500)
    
class PedidoCreate(PedidoBase):
    """
    Schema para crear un pedido.
    Incluye la lista de detalles (productos).
    """
    detalles: List[DetallePedidoCreate]
    
class PedidoUpdate(SQLModel):
    """
    Schema para actualizar un pedido.
    Solo ciertos campos pueden modificarse.
    """
    direccion_entrega_id: Optional[int] = None
    forma_pago_id: Optional[int] = None
    notas_cliente: Optional[str] = None
    
class PedidoPublic(PedidoBase):
    id: int
    usuario_id: int
    estado_id: int
    estado_codigo: EstadoPedidoEnum
    subtotal: Decimal
    costo_envio: Decimal
    total: Decimal
    #fecha_entrega_estimada: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    
    # Detalles embebidos
    detalles: List[DetallePedidoPublic] = []
    
class PedidoList(SQLModel):
    """
    Respuesta de listado de pedidos con paginación.
    """
    data: List[PedidoPublic]
    total: int
    
class HistorialEstadoPedidoBase(SQLModel):
    estado_id: int
    observaciones: Optional[str] = Field(default=None, max_length=500)
    
class HistorialEstadoPedidoCreate(HistorialEstadoPedidoBase):
    pass

class HistorialEstadoPedidoPublic(HistorialEstadoPedidoBase):
    id: int
    pedido_id: int
    usuario_cambio_id: Optional[int]
    fecha_cambio: datetime
    estado_codigo: Optional[str] = None
    
class CambioEstadoRequest(SQLModel):
    """
    Request para cambiar el estado de un pedido.
    """
    nuevo_estado: EstadoPedidoEnum
    observaciones: Optional[str] = Field(default=None, max_length=500)