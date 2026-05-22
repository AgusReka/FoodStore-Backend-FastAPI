from sqlmodel import SQLModel, Field
from typing import Optional
from datetime import datetime

class UserRol(SQLModel, table=True):
    __tablename__ = "user_roles"

    # PK compuesta
    id_user: int = Field(foreign_key="user.id", primary_key=True)
    rol_code: str = Field(foreign_key="roles.code", primary_key=True)

    # Atributos
    assigned_by_id: Optional[int] = Field(default=None, foreign_key="user.id")
    expires_at:      Optional[datetime] = Field(default=None)

    # Audit
    created_at: datetime = Field(default_factory=datetime.utcnow)