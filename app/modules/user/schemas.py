from sqlmodel import SQLModel, Field
from pydantic import EmailStr
from typing import Optional
from datetime import datetime

# ─── Esquemas Pydantic (sin table=True) ──────────────────────────────────────

class UserCreate(SQLModel):
    """Datos requeridos para registrar un usuario."""
    username:  str
    full_name: str
    email:     EmailStr
    password:  str = Field(min_length=8)


class RolPublic(SQLModel):
    """Vista pública de un rol."""
    codigo:      str
    nombre:      str
    descripcion: Optional[str] = None


class UsuarioRolPublic(SQLModel):
    """Vista pública de un rol asignado al usuario."""
    rol_code:       str
    expires_at:     Optional[datetime] = None
    created_at:     datetime


class AsignarRolInput(SQLModel):
    """Body para asignar un rol a un usuario."""
    rol_code:      str
    expires_at:      Optional[datetime] = None


class UserPublic(SQLModel):
    """Vista pública del usuario — excluye hashed_password."""
    id:        int
    username:  str
    full_name: str
    email:     str
    #role:      str
    disabled:  bool
    roles:     list[UsuarioRolPublic] = []   # ← roles asignados


class Token(SQLModel):
    """Respuesta del endpoint /token."""
    access_token: str
    token_type:   str = "bearer"
    expires_in:   int
