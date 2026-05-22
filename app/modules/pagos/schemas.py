from typing import Optional, List
from sqlmodel import SQLModel, Field
from datetime import datetime

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