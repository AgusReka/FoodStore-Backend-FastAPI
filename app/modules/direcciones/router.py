from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Annotated, Optional, List
from sqlmodel import Session
from app.core.database import get_session
from app.core.deps import get_current_active_user, require_admin_or_pedidos
from app.modules.user.models import User
from app.modules.direcciones.service import DireccionesService
from app.modules.direcciones.schemas import (
    DireccionEntregaCreate,
    DireccionEntregaUpdate,
    DireccionEntregaPublic,
    DireccionEntregaList
)

router = APIRouter(
    tags=["Direcciones"],
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Acceso denegado"},
        404: {"description": "Dirección no encontrada"}
    }
)

def get_direcciones_service(session: Session = Depends(get_session)) -> DireccionesService:
    """Factory de dependencia: inyecta el servicio con su Session."""
    return DireccionesService(session)

@router.get(
    "/",
    response_model=DireccionEntregaList,
    summary="Listar mis direcciones",
    description="Obtiene todas las direcciones de entrega del usuario."
)
def list_direcciones(
    current_user: Annotated[User, Depends(get_current_active_user)],
    svc: DireccionesService = Depends(get_direcciones_service),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100)
) -> DireccionEntregaList:
    """LISTADO: Solo direcciones del usuario autenticado."""
    direcciones = svc.get_direcciones_by_usuario(
        usuario_id=current_user.id,
        offset=offset,
        limit=limit
    )
    total = svc.count_direcciones_by_usuario(current_user.id)
    return DireccionEntregaList(data=direcciones, total=total)

@router.get(
    "/admin/usuario/{usuario_id}",
    response_model=DireccionEntregaList,
    summary="[ADMIN/PEDIDOS] Listar direcciones de un usuario",
    description="Vista administrativa: lista direcciones de cualquier usuario por ID."
)
def admin_list_direcciones_by_usuario(
    usuario_id: int,
    _: Annotated[User, Depends(require_admin_or_pedidos)],
    svc: DireccionesService = Depends(get_direcciones_service),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100)
) -> DireccionEntregaList:
    """Solo ADMIN o PEDIDOS pueden consultar direcciones ajenas."""
    direcciones = svc.get_direcciones_by_usuario(
        usuario_id=usuario_id,
        offset=offset,
        limit=limit
    )
    total = svc.count_direcciones_by_usuario(usuario_id)
    return DireccionEntregaList(data=direcciones, total=total)


@router.get(
    "/principal",
    response_model=Optional[DireccionEntregaPublic],
    summary="Obtener dirección principal",
    description="Obtiene la dirección marcada como principal del usuario (si tiene)."
)
def get_direccion_principal(
    current_user: Annotated[User, Depends(get_current_active_user)],
    svc: DireccionesService = Depends(get_direcciones_service)
) -> Optional[DireccionEntregaPublic]:
    """Retorna null si el usuario no tiene dirección principal configurada."""
    return svc.get_direccion_principal(usuario_id=current_user.id)

@router.get(
    "/{direccion_id}",
    response_model=DireccionEntregaPublic,
    summary="Obtener dirección por ID",
    description="Obtiene una dirección específica validando que pertenezca al usuario."
)
def get_direccion(
    direccion_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    svc: DireccionesService = Depends(get_direcciones_service)
) -> DireccionEntregaPublic:
    """Un usuario NO puede acceder a direcciones de otro usuario."""
    return svc.get_direccion_by_id(
        direccion_id=direccion_id,
        usuario_id=current_user.id
    )
    
@router.post(
    "/",
    response_model=DireccionEntregaPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nueva dirección",
    description="Agrega una nueva dirección de entrega para el usuario."
)
def create_direccion(
    direccion_in: DireccionEntregaCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    svc: DireccionesService = Depends(get_direcciones_service)
) -> DireccionEntregaPublic:
    """
    Si es_principal=True, automáticamente desmarca otras direcciones principales.
    Un usuario puede tener múltiples direcciones pero solo una principal.
    """
    return svc.create_direccion(
        usuario_id=current_user.id,
        direccion_in=direccion_in
    )  
    
@router.patch(
    "/{direccion_id}",
    response_model=DireccionEntregaPublic,
    summary="Actualizar dirección",
    description="Modifica los datos de una dirección existente."
)
def update_direccion(
    direccion_id: int,
    direccion_in: DireccionEntregaUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    svc: DireccionesService = Depends(get_direcciones_service)
) -> DireccionEntregaPublic:
    """
    Solo el propietario puede modificar su dirección.
    Si se cambia es_principal, se actualiza la relación automáticamente.
    """
    return svc.update_direccion(
        direccion_id=direccion_id,
        usuario_id=current_user.id,
        direccion_in=direccion_in
    )
    
@router.patch(
    "/{direccion_id}/principal",
    response_model=DireccionEntregaPublic,
    summary="Marcar como dirección principal",
    description="Establece esta dirección como la principal del usuario (desmarca las demás)."
)
def marcar_principal(
    direccion_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    svc: DireccionesService = Depends(get_direcciones_service)
) -> DireccionEntregaPublic:
    """Endpoint específico para cambiar la dirección principal sin enviar todos los campos."""
    return svc.marcar_como_principal(
        direccion_id=direccion_id,
        usuario_id=current_user.id
    )
    
@router.delete(
    "/{direccion_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Eliminar dirección (soft delete)",
    description="Marca la dirección como eliminada lógicamente (deleted_at)."
)
def delete_direccion(
    direccion_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    svc: DireccionesService = Depends(get_direcciones_service)
) -> None:
    svc.delete_direccion(
        direccion_id=direccion_id,
        usuario_id=current_user.id
    )
    return None