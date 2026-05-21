from typing import Optional, List
from sqlmodel import SQLModel, Field
from datetime import datetime

class DireccionEntregaBase(SQLModel):
    alias: str = Field(max_length=50)
    calle: str = Field(max_length=200)
    numero: str = Field(max_length=20)
    piso_dpto: Optional[str] = Field(default=None, max_length=50)
    ciudad: str = Field(max_length=100)
    provincia: str = Field(max_length=100)
    codigo_postal: Optional[str] = Field(default=None, max_length=20)
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    referencias: Optional[str] = Field(default=None, max_length=500)
    
class DireccionEntregaCreate(DireccionEntregaBase):
    es_principal: bool = False
    
class DireccionEntregaUpdate(SQLModel):
    alias: Optional[str] = Field(default=None, max_length=50)
    calle: Optional[str] = Field(default=None, max_length=200)
    numero: Optional[str] = Field(default=None, max_length=20)
    piso_dpto: Optional[str] = Field(default=None, max_length=50)
    ciudad: Optional[str] = Field(default=None, max_length=100)
    provincia: Optional[str] = Field(default=None, max_length=100)
    codigo_postal: Optional[str] = Field(default=None, max_length=20)
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    referencias: Optional[str] = Field(default=None, max_length=500)
    es_principal: Optional[bool] = None
    
class DireccionEntregaPublic(DireccionEntregaBase):
    id: int
    usuario_id: int
    es_principal: bool
    is_active: bool
    created_at: datetime
    updated_at: datetime
    deleted_at: Optional[datetime] = None
    
class DireccionEntregaList(SQLModel):
    data: List[DireccionEntregaPublic]
    total: int