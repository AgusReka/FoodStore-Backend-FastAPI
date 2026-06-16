from typing import Optional, List
from sqlmodel import SQLModel, Field
from datetime import datetime
from decimal import Decimal

class FormaPagoBase(SQLModel):
    nombre: str = Field(max_length=100)
    descripcion: Optional[str] = None
    requiere_monto_pago: bool = False

class FormaPagoCreate(FormaPagoBase):
    pass

class FormaPagoUpdate(SQLModel):
    nombre: Optional[str] = Field(default=None, max_length=100)
    descripcion: Optional[str] = None
    requiere_monto_pago: Optional[bool] = None
    is_active: Optional[bool] = None

class FormaPagoPublic(FormaPagoBase):
    id: int
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None

class FormaPagoList(SQLModel):
    data: List[FormaPagoPublic]
    total: int


class CrearPreferenciaRequest(SQLModel):
    pedido_id: int

class CrearPreferenciaResponse(SQLModel):
    init_point: str
    preference_id: str

class ConfirmarPagoRequest(SQLModel):
    pedido_id: int
    payment_id: Optional[int] = None

class PagoMPStatusResponse(SQLModel):
    estado: str
    pedido_id: int

class PagoMPPublic(SQLModel):
    id: int
    pedido_id: int
    mp_payment_id: Optional[int]
    mp_status: str
    mp_status_detail: Optional[str]
    transaction_amount: Decimal
    external_reference: str
    created_at: datetime
    updated_at: datetime