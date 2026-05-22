"""
Modelo de Usuario — tabla 'usuario' en PostgreSQL.

Campos clave para seguridad:
  - hashed_password: hash bcrypt (nunca texto plano).
  - role: "user" | "admin" — usado por require_role() para RBAC.
  - disabled: permite desactivar cuentas sin eliminarlas.
"""

from sqlmodel import SQLModel, Field, Relationship
from typing import Optional, List
from app.modules.user.user_rol import UserRol

class User(SQLModel, table=True):
    id:              Optional[int] = Field(default=None, primary_key=True)
    username:        str           = Field(index=True, unique=True)
    full_name:       str
    email:           str           = Field(index=True, unique=True)
    hashed_password: str
    #role:            str           = Field(default="CLIENT")
    disabled:        bool          = Field(default=False)

    # Relación hacia UsuarioRol
    roles: List["UserRol"] = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "UserRol.id_user",
            "lazy": "selectin"
        }
    )