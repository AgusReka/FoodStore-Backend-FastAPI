"""
Repositorio de User.

Acceso a BD: queries sin lógica de negocio.
Hereda de BaseRepository[User] y agrega queries específicas.

Capa: Repository
Conoce a: Model (User), Session
NO conoce a: Service, Router
"""

from sqlmodel import Session, select
from datetime import datetime

from app.core.repository import BaseRepository
from app.modules.user.models import User
from app.modules.user.rol import Rol
from app.modules.user.user_rol import UserRol


class UserRepository(BaseRepository[User]):

    def __init__(self, session: Session):
        super().__init__(session, User)

    def get_by_username(self, username: str) -> User | None:
        return self.session.exec(
            select(User).where(User.username == username)
        ).first()

    def get_by_email(self, email: str) -> User | None:
        return self.session.exec(
            select(User).where(User.email == email)
        ).first()

 # ─── Roles ────────────────────────────────────────────────────────────────

    def get_roles(self, id_user: int) -> list[UserRol]:
        return list(self.session.exec(
            select(UserRol).where(UserRol.id_user == id_user)  # ← UserRol, no Rol
        ).all())

    def get_rol(self, code: str) -> Rol | None:
        return self.session.get(Rol, code)  # ← Rol está bien acá (es el catálogo)

    def asignar_rol(
        self,
        id_user: int,
        rol_code: str,
        asignado_por_id: int | None = None,
        expires_at: datetime | None = None,
    ) -> UserRol:
        existing = self.session.exec(
            select(UserRol).where(           # ← UserRol, no Rol
                UserRol.id_user == id_user,
                UserRol.rol_code == rol_code,
            )
        ).first()
        if existing:
            return existing

        user_rol = UserRol(                  # ← UserRol, no Rol
            id_user=id_user,
            rol_code=rol_code,
            assigned_by_id=asignado_por_id,  # ← assigned_by_id, no asignado_por_id
            expires_at=expires_at,
        )
        self.session.add(user_rol)
        return user_rol

    def quitar_rol(self, id_user: int, rol_code: str) -> bool:
        registro = self.session.exec(
            select(UserRol).where(           # ← UserRol, no Rol
                UserRol.id_user == id_user,
                UserRol.rol_code == rol_code,
            )
        ).first()
        if not registro:
            return False
        self.session.delete(registro)
        return True