from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..pedidos.models import Pedido

class DireccionEntrega(SQLModel, table=True):
    """
    Direcciones de entrega de los usuarios.
    Cada usuario puede tener múltiples direcciones, pero solo una principal.
    """
    __tablename__ = "direccion"
    
    id: Optional[int] = Field(default=None, primary_key=True)
    usuario_id: int = Field(nullable=False)
    # Alias para identificar la dirección (Casa, Trabajo, etc.)
    alias: str = Field(
        max_length=50,
        nullable=False,
        description="Alias para identificar"
    )
    
    # Datos de la dirección
    calle: str = Field(max_length=100, nullable=False)
    numero: str = Field(max_length=20, nullable=False)
    piso_dpto: Optional[str] = Field(
        default= None,
        max_length=20,
        description="Piso y departamento (opcional)"
    )
    ciudad: str = Field(max_length=50, nullable=False)
    provincia: str = Field(max_length=50, nullable=False)
    codigo_postal: str = Field(max_length=20, nullable=False)
    # Coordenadas (opcional para mapas)
    latitud: Optional[float] = None
    longitud: Optional[float] = None
    # Indica si es la dirección principal del usuario
    es_principal: bool = Field(
        default=False,
        description="Solo una dirección por usuario puede ser principal"
    )
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deleted_at: Optional[datetime] = Field(default=None)
    
    # Relación con Pedido
    pedidos: List["Pedido"] = Relationship(back_populates="direccion")