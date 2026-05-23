"""
Dependencias de autenticación y autorización para FastAPI.

Este módulo define funciones que se inyectan con Depends() para:
- Extraer el token JWT desde el request
- Validar autenticación
- Validar estado del User
- Validar permisos (roles)

Flujo de ejecución típico:

    Request HTTP
        ↓
    oauth2_scheme → extrae el token Bearer del header Authorization
        ↓
    get_current_user → decodifica el JWT y busca el User en DB
        ↓
    get_current_active_user → valida que el User esté activo
        ↓
    require_role([...]) → valida permisos (RBAC)

Convenciones HTTP:
    401 → No autenticado (token inválido, ausente o expirado)
    403 → Autenticado pero sin permisos suficientes

Arquitectura:
    - Capa Core (dependencias reutilizables)
    - Depende de:
        * Unit of Work (acceso a datos)
        * Seguridad (JWT)
        * Modelo User
"""

from typing import Annotated  # Permite tipado enriquecido para Depends

from fastapi import Depends, HTTPException, status  # Inyección y manejo de errores HTTP
from fastapi.security import OAuth2PasswordBearer  # Manejo estándar de OAuth2 con Bearer

from app.core.roles import RoleCode  # Enum de códigos de rol (fuente de verdad)
from app.core.security import decode_access_token  # Función para decodificar JWT
from app.core.unit_of_work import UnitOfWork, get_uow       # Patrón Unit of Work para DB
from app.modules.user.models import User     # Modelo de dominio User

from fastapi import Request

class OAuth2PasswordBearerWithCookie(OAuth2PasswordBearer):
    async def __call__(self, request: Request) -> str | None:
        # 1. Obtener el token EXCLUSIVAMENTE de la cookie (HttpOnly)
        token = request.cookies.get("access_token")
        
        # 2. El soporte para el header Authorization fue deshabilitado.
        # ¿Por qué? Para maximizar la seguridad y forzar el uso de cookies HttpOnly.
        # Las cookies HttpOnly no pueden ser leídas por JavaScript (mitigando ataques XSS).
        # Si permitiéramos usar el token vía header, el frontend tendría que manipular
        # el token en texto plano, arruinando el propósito de la cookie HttpOnly.
        # 
        # if not token:
        #     authorization = request.headers.get("Authorization")
        #     if authorization and authorization.startswith("Bearer "):
        #         token = authorization.split(" ")[1]
                
        if not token:
            if self.auto_error:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="No autenticado",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            else:
                return None
        return token

# Define el esquema OAuth2 que extrae el token de la cookie (o header)
oauth2_scheme = OAuth2PasswordBearerWithCookie(tokenUrl="/api/v1/auth/token")



async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],  # Token extraído automáticamente
    uow: Annotated[UnitOfWork, Depends(get_uow)],   # Inyección del Unit of Work
):
    """
    Decodifica el JWT y retorna el User correspondiente.

    Responsabilidades:
    - Validar token
    - Extraer identidad (username)
    - Buscar User en base de datos
    """

    # Excepción estándar para errores de autenticación (401)
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Credenciales inválidas o token expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )

    # Decodifica el JWT → devuelve payload o None si es inválido
    payload = decode_access_token(token)
    if payload is None:
        raise credentials_exception

    # Extrae el "subject" (User) del token
    username: str | None = payload.get("sub")
    if username is None:
        raise credentials_exception

    # Abre contexto de Unit of Work (manejo de sesión/transacción)
    with uow:
        # Busca el User en base de datos
        user = uow.users.get_by_username(username)

        # Si no existe el User → token inválido
        if user is None:
            raise credentials_exception

        user._roles_from_token = payload.get("roles", [])
        return user  # User autenticado válido


async def get_current_active_user(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """
    Verifica que el User autenticado esté activo.

    Regla de negocio:
    - Un User con disabled=True no puede operar
    """

    if current_user.disabled:
        # Error semántico: el User existe pero no puede operar
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cuenta de User desactivada",
        )

    return current_user # User válido y activo


def require_role(allowed_roles: list[RoleCode]):
    """
    Factory de dependencias para control de acceso basado en roles (RBAC).

    Genera dinámicamente una dependencia que valida si el User
    tiene uno de los roles permitidos.

    Parámetros:
        allowed_roles → lista de RoleCode permitidos (ej: [RoleCode.ADMIN])

    Uso típico:
        @router.get("/admin", dependencies=[Depends(require_role([RoleCode.ADMIN]))])

    Para los casos más comunes preferí los helpers preconfigurados
    (`require_admin`, `require_admin_or_stock`, `require_admin_or_pedidos`).
    """

    async def role_checker(
        current_user: Annotated[User, Depends(get_current_active_user)],
    ) -> User:
        """
        Valida que el rol del User esté dentro de los permitidos.
        """
        user_roles: list[str] = getattr(current_user, "_roles_from_token", [])
        # Si el rol del User no está permitido → 403 (prohibido)
        if not any(r in allowed_roles for r in user_roles):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Permisos insuficientes. Tus roles son: {user_roles}. "
                    f"Se requiere uno de: {allowed_roles}"
                ),
            )

        return current_user  # User autorizado

    return role_checker  # Retorna la dependencia configurada


# ─── Dependencias preconfiguradas (atajos para combinaciones frecuentes) ─────
# Evitan repetir literals de roles en cada router y permiten refactor seguro.

require_admin = require_role([RoleCode.ADMIN])
require_admin_or_stock = require_role([RoleCode.ADMIN, RoleCode.STOCK])
require_admin_or_pedidos = require_role([RoleCode.ADMIN, RoleCode.PEDIDOS])