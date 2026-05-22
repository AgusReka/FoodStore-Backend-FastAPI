"""
Router de autenticación y gestión de Users.

HTTP puro: parsear request, validar schema Pydantic, delegar al Service,
serializar response con response_model. No contiene lógica de negocio.

Capa: Router
Conoce a: Service (vía UoW)
NO conoce a: Repository, Model (solo esquemas Pydantic para response_model)

Regla de imports:
    Router → Service → UoW → Repository → Model
"""

from typing import Annotated

from fastapi import APIRouter, Depends, status, Response
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session

from app.core.database import get_session
from app.core.deps import get_current_active_user, require_role
from app.modules.user.models import User
from app.modules.user.schemas import UserCreate, UserPublic, Token, AsignarRolInput, UsuarioRolPublic
from app.modules.user.service import UserService

router = APIRouter()

def get_user_service(session: Session = Depends(get_session)) -> UserService:
    """Factory de dependencia: inyecta el servicio con su Session."""
    return UserService(session)

# ─── Registro ─────────────────────────────────────────────────────────────────

@router.post("/register", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def register(
    user_in: UserCreate,
    service: Annotated[UserService, Depends(get_user_service)],
):
    return service.register(user_in)


# ─── Login (OAuth2 Password Flow) ────────────────────────────────────────────

@router.post("/token")
def login(
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
    service: Annotated[UserService, Depends(get_user_service)],
    response: Response,
):
    token = service.authenticate(form_data.username, form_data.password)
    
    # Configuramos la cookie HttpOnly
    response.set_cookie(
        key="access_token",
        value=token.access_token,
        httponly=True,
        max_age=1800,  # 30 minutos, o el valor de expires_in
        samesite="lax",
        secure=False,  # En producción con HTTPS debería ser True
    )
    return {"mensaje": "Login exitoso. Sesión iniciada."}

@router.post("/logout")
def logout(response: Response):
    # Limpiar la cookie HttpOnly al cerrar sesión
    response.delete_cookie(
        key="access_token",
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return {"mensaje": "Sesión cerrada exitosamente"}


# ─── Rutas protegidas ────────────────────────────────────────────────────────

@router.get("/me", response_model=UserPublic)
def read_me(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    return current_user


"""@router.get("/privado")
def ruta_privada(
    current_user: Annotated[User, Depends(get_current_active_user)],
):
    roles_codigos = [ur.rol_code for ur in current_user.roles]
    return {
        "mensaje": f"¡Hola, {current_user.full_name}! Accediste a una ruta privada.",
        "roles": roles_codigos,
    }"""


# ─── Rutas de administración (RBAC) ──────────────────────────────────────────

@router.get("/admin/users", response_model=list[UserPublic])
def list_users(
    _admin: Annotated[User, Depends(require_role(["ADMIN"]))],
    service: Annotated[UserService, Depends(get_user_service)],
):
    return service.list_all()


@router.post("/admin/users/desactivar/{user_id}", response_model=UserPublic)
def deactivate_user(
    user_id: int,
    _admin: Annotated[User, Depends(require_role(["ADMIN"]))],
    service: Annotated[UserService, Depends(get_user_service)],
):
    return service.set_disabled(user_id, disabled=True)


@router.post("/admin/users/activar/{user_id}", response_model=UserPublic)
def activate_user(
    user_id: int,
    _admin: Annotated[User, Depends(require_role(["ADMIN"]))],
    service: Annotated[UserService, Depends(get_user_service)],
):
    return service.set_disabled(user_id, disabled=False)

# ─── Gestión de roles ─────────────────────────────────────────────────────────

@router.get("/admin/users/roles/{user_id}", response_model=list[UsuarioRolPublic])
def get_roles(
    user_id: int,
    _admin: Annotated[User, Depends(require_role(["ADMIN"]))],
    service: Annotated[UserService, Depends(get_user_service)],
):
    return service.get_roles(user_id)


@router.post("/admin/users/asignar/{user_id}",
             response_model=UsuarioRolPublic, status_code=status.HTTP_201_CREATED)
def asignar_rol(
    user_id: int,
    data: AsignarRolInput,
    admin: Annotated[User, Depends(require_role(["ADMIN"]))],
    service: Annotated[UserService, Depends(get_user_service)],
):
    return service.asignar_rol(user_id, data, asignado_por_id=admin.id)


@router.delete("/admin/users/{user_id}/roles/{rol_codigo}",
               status_code=status.HTTP_204_NO_CONTENT)
def quitar_rol(
    user_id: int,
    rol_codigo: str,
    _admin: Annotated[User, Depends(require_role(["ADMIN"]))],
    service: Annotated[UserService, Depends(get_user_service)],
):
    service.quitar_rol(user_id, rol_codigo)
