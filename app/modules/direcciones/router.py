from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Annotated, Optional, List
from sqlmodel import Session
#from app.core.database import get_db
#from app.core.dependencies import get_current_user
#from app.modules.usuario.models import Usuario
from app.modules.direcciones.service import DireccionesService
from app.modules.direcciones.schemas import (
    DireccionEntregaCreate,
    DireccionEntregaUpdate,
    DireccionEntregaPublic,
    DireccionEntregaList
)

router = APIRouter(
    prefix="/direcciones",
    tags=["Direcciones"],
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Acceso denegado"},
        404: {"description": "Dirección no encontrada"}
    }
)

# @router.get(
#     "/",
#     response_model=DireccionEntregaList,
#     summary="Listar mis direcciones",
#     description="Obtiene todas las direcciones de entrega del usuario autenticado."
# )
# async def list_direcciones(
#     current_user: Annotated[Usuario, Depends(get_current_user)],
#     db: Annotated[Session, Depends(get_db)],
#     offset: Annotated[int, Query(ge=0)] = 0,
#     limit: Annotated[int, Query(ge=1, le=100)] = 20
# ) -> DireccionEntregaList:
#     """LISTADO: Solo direcciones del usuario autenticado."""
#     service = DireccionesService(db)
#     direcciones = service.get_direcciones_by_usuario(
#         usuario_id=current_user.id,
#         offset=offset,
#         limit=limit
#     )
#     total = service.uow.direcciones.count_by_usuario(current_user.id)
    
#     return DireccionEntregaList(data=direcciones, total=total)

# @router.get(
#     "/principal",
#     response_model=DireccionEntregaPublic,
#     summary="Obtener dirección principal",
#     description="Obtiene la dirección marcada como principal del usuario (si tiene)."
# )
# async def get_direccion_principal(
#     current_user: Annotated[Usuario, Depends(get_current_user)],
#     db: Annotated[Session, Depends(get_db)]
# ) -> Optional[DireccionEntregaPublic]:
#     """
#     Retorna null si el usuario no tiene dirección principal configurada
#     """
#     service = DireccionesService(db)
#     return service.get_direccion_principal(usuario_id=current_user.id)

# @router.get(
#     "/{direccion_id}",
#     response_model=DireccionEntregaPublic,
#     summary="Obtener dirección por ID",
#     description="Obtiene una dirección específica validando que pertenezca al usuario."
# )
# async def get_direccion(
#     direccion_id: int,
#     current_user: Annotated[Usuario, Depends(get_current_user)],
#     db: Annotated[Session, Depends(get_db)]
# ) -> DireccionEntregaPublic:
#     """
#     Un usuario NO puede acceder a direcciones de otro usuario.
#     """
#     service = DireccionesService(db)
#     return service.get_direccion_by_id(
#         direccion_id=direccion_id,
#         usuario_id=current_user.id
#     )
    
# @router.post(
#     "/",
#     response_model=DireccionEntregaPublic,
#     status_code=status.HTTP_201_CREATED,
#     summary="Crear nueva dirección",
#     description="Agrega una nueva dirección de entrega para el usuario autenticado."
# )
# async def create_direccion(
#     direccion_in: DireccionEntregaCreate,
#     current_user: Annotated[Usuario, Depends(get_current_user)],
#     db: Annotated[Session, Depends(get_db)]
# ) -> DireccionEntregaPublic:
#     """
#     Si es_principal=True, automáticamente desmarca otras direcciones principales
#     Un usuario puede tener múltiples direcciones pero solo una principal.
#     """
#     service = DireccionesService(db)
#     return service.create_direccion(
#         usuario_id=current_user.id,
#         direccion_in=direccion_in
#     )  
    
# @router.patch(
#     "/{direccion_id}",
#     response_model=DireccionEntregaPublic,
#     summary="Actualizar dirección",
#     description="Modifica los datos de una dirección existente."
# )
# async def update_direccion(
#     direccion_id: int,
#     direccion_in: DireccionEntregaUpdate,
#     current_user: Annotated[Usuario, Depends(get_current_user)],
#     db: Annotated[Session, Depends(get_db)]
# ) -> DireccionEntregaPublic:
#     """
#     Solo el propietario puede modificar su dirección
#     Si se cambia es_principal, se actualiza la relación automáticamente
#     """
#     service = DireccionesService(db)
#     return service.update_direccion(
#         direccion_id=direccion_id,
#         usuario_id=current_user.id,
#         direccion_in=direccion_in
#     )
    
# @router.patch(
#     "/{direccion_id}/principal",
#     response_model=DireccionEntregaPublic,
#     summary="Marcar como dirección principal",
#     description="Establece esta dirección como la principal del usuario (desmarca las demás)."
# )
# async def marcar_principal(
#     direccion_id: int,
#     current_user: Annotated[Usuario, Depends(get_current_user)],
#     db: Annotated[Session, Depends(get_db)]
# ) -> DireccionEntregaPublic:
#     """
#     Endpoint específico para cambiar la dirección principal sin enviar todos los campos
#     Más limpio y semántico que un PATCH genérico
#     """
#     service = DireccionesService(db)
#     return service.marcar_como_principal(
#         direccion_id=direccion_id,
#         usuario_id=current_user.id
#     )
    
# @router.delete(
#     "/{direccion_id}",
#     status_code=status.HTTP_204_NO_CONTENT,
#     summary="Eliminar dirección (soft delete)",
#     description="Marca la dirección como eliminada lógicamente (deleted_at)."
# )
# async def delete_direccion(
#     direccion_id: int,
#     current_user: Annotated[Usuario, Depends(get_current_user)],
#     db: Annotated[Session, Depends(get_db)]
# ) -> None:
#     service = DireccionesService(db)
#     service.delete_direccion(
#         direccion_id=direccion_id,
#         usuario_id=current_user.id
#     )
#     return None