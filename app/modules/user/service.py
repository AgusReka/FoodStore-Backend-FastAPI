"""
Service de user — lógica de negocio.

Stateless, orquesta operaciones sobre los repositorios a través del UoW.
Lanza HTTPException. No hace commit/rollback directamente.

Capa: Service
Conoce a: UoW, Repository (indirectamente vía UoW)
NO conoce a: Router

Regla de imports:
    Router → Service → UoW → Repository → Model
"""

from app.core import database
from fastapi import HTTPException, status
from sqlmodel import Session

from app.core.config import settings
from app.core.security import hash_password, verify_password, create_access_token
from app.modules.user.unit_of_work import UserUnitOfWork
from app.modules.user.models import User
from app.modules.user.schemas import UserCreate, Token, UserPublic, AsignarRolInput
from app.modules.user.user_rol import UserRol


class UserService:
    """Lógica de negocio para autenticación y gestión de users."""

    def __init__(self, session: Session):
        self._session = session

    def register(self, user_in: UserCreate) -> UserPublic:
        with UserUnitOfWork(self._session) as uow:
            if uow.users.get_by_username(user_in.username):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail="El nombre de user ya está en uso")
            if uow.users.get_by_email(user_in.email):
                raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                    detail="El email ya está registrado")

            user = User(
                username=user_in.username,
                full_name=user_in.full_name,
                email=user_in.email,
                hashed_password=hash_password(user_in.password),
            )
            uow.users.add(user)

            # Asignar CLIENT automáticamente
            uow.users.asignar_rol(id_user=user.id, rol_code="CLIENT")
            uow.refresh(user)   # recarga para que roles esté populated (hace flush implícito)

            return UserPublic.model_validate(user)

    def authenticate(self, username: str, password: str) -> Token:
        with UserUnitOfWork(self._session) as uow:
            user = uow.users.get_by_username(username)

            if not user or not verify_password(password, user.hashed_password):
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                    detail="Credenciales incorrectas",
                                    headers={"WWW-Authenticate": "Bearer"})
            if user.disabled:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail="Cuenta desactivada")

            # Leer roles desde la tabla user_roles
            roles_codigos = [ur.rol_code for ur in uow.users.get_roles(user.id)]

            access_token = create_access_token(
                data={"sub": user.username, "roles": roles_codigos}  # ← lista, no string
            )
            return Token(access_token=access_token, token_type="bearer",
                        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)

    def list_all(self) -> list[User]:
        """Lista todos los users."""
        with UserUnitOfWork(self._session) as uow:
            return uow.users.get_all()

    def set_disabled(self, user_id: int, disabled: bool) -> User:
        """Activa o desactiva la cuenta de un user."""
        with UserUnitOfWork(self._session) as uow:
            user = uow.users.get_by_id(user_id)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="user no encontrado",
                )
            user.disabled = disabled
            return uow.users.update(user)

# ─── Roles ────────────────────────────────────────────────────────────────

    def get_roles(self, usuario_id: int) -> list["UserRol"]:
        with UserUnitOfWork(self._session) as uow:
            self._verificar_usuario(usuario_id, uow)
            return uow.users.get_roles(usuario_id)

    def asignar_rol(
        self,
        usuario_id: int,
        data: AsignarRolInput,
        asignado_por_id: int,
    ) -> UserRol:
        with UserUnitOfWork(self._session) as uow:
            self._verificar_usuario(usuario_id, uow)

            if not uow.users.get_rol(data.rol_code):
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                    detail=f"Rol '{data.rol_code}' no existe")

            ur = uow.users.asignar_rol(
                id_user=usuario_id,
                rol_code=data.rol_code,
                asignado_por_id=asignado_por_id,
                expires_at=data.expires_at,
            )
            return ur

    def quitar_rol(self, usuario_id: int, rol_code: str) -> None:
        with UserUnitOfWork(self._session) as uow:
            self._verificar_usuario(usuario_id, uow)
            eliminado = uow.users.quitar_rol(usuario_id, rol_code)
            if not eliminado:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                    detail="El usuario no tiene ese rol")

    # ─── Helpers privados ─────────────────────────────────────────────────────

    def _verificar_usuario(self, user_id: int, uow: UserUnitOfWork) -> User:
        user = uow.users.get_by_id(user_id)
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                                detail="Usuario no encontrado")
        return user

    def _to_public(self, user: User, uow: UserUnitOfWork) -> UserPublic:
        """Arma UserPublic incluyendo los roles actuales del usuario."""
        roles = uow.users.get_roles(user.id) if user.id else []
        return UserPublic(
            id=user.id,
            username=user.username,
            full_name=user.full_name,
            email=user.email,
            disabled=user.disabled,
            roles=roles,
        )