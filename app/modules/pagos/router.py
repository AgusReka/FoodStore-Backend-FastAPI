from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Annotated, Optional, List
from app.core.database import get_session
from sqlmodel import Session

#from app.core.database import get_db
#from app.core.dependencies import get_current_user, require_role
#from app.modules.usuario.models import Usuario
from app.modules.pagos.service import FormaPagoService
from app.modules.pagos.schemas import (
    FormaPagoCreate,
    FormaPagoUpdate,
    FormaPagoPublic,
    FormaPagoList
)

router = APIRouter(
    prefix="/formas-pago",
    tags=["Formas de Pago"],
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Acceso denegado"},
        404: {"description": "Recurso no encontrado"}
    }
)

def get_forma_pago_service(session: Session = Depends(get_session)) -> FormaPagoService:
    """Factory de dependencia: inyecta el servicio con su Session."""
    return FormaPagoService(session)

# @router.get(
#     "/",
#     response_model=FormaPagoList,
#     summary="Listar formas de pago disponibles",
#     description="Obtiene todas las formas de pago activas para mostrar en checkout."
# )
# async def list_formas_pago(
#     db: Annotated[Session, Depends(get_pagos_service)],
#     offset: Annotated[int, Query(ge=0)] = 0,
#     limit: Annotated[int, Query(ge=1, le=100)] = 20
# ) -> FormaPagoList:
#     """
#     Cualquier usuariopuede consultar las formas de pago disponibles.
#     """
#     service = FormaPagoService(db)
#     formas_pago = service.get_formas_pago_activas()
    
#     return FormaPagoList(
#         data=formas_pago[offset:offset+limit],
#         total=len(formas_pago)
#     )
    
# @router.get(
#     "/{forma_pago_id}",
#     response_model=FormaPagoPublic,
#     summary="Obtener forma de pago por ID",
#     description="Obtiene los detalles de una forma de pago específica."
# )
# async def get_forma_pago(
#     forma_pago_id: int,
#     db: Annotated[Session, Depends(get_db)]
# ) -> FormaPagoPublic:
#     """Consulta pública de una forma de pago por ID."""
#     service = FormaPagoService(db)
#     return service.get_forma_pago_by_id(forma_pago_id)

# @router.post(
#     "/",
#     response_model=FormaPagoPublic,
#     status_code=status.HTTP_201_CREATED,
#     summary="[ADMIN] Crear forma de pago",
#     description="Agrega una nueva forma de pago al sistema. Solo ADMIN."
# )
# async def create_forma_pago(
#     forma_pago_in: FormaPagoCreate,
#     current_user: Annotated[Usuario, Depends(lambda: require_role(["ADMIN"]))],
#     db: Annotated[Session, Depends(get_db)]
# ) -> FormaPagoPublic:
#     """
#     Solo accesible para rol ADMIN
#     Valida unicidad del nombre
#     Configura si requiere monto exacto (ej: efectivo)
#     """
#     service = FormaPagoService(db)
#     return service.create_forma_pago(
#         forma_pago_in=forma_pago_in,
#         es_admin=True
#     )
    
# @router.patch(
#     "/{forma_pago_id}",
#     response_model=FormaPagoPublic,
#     summary="[ADMIN] Actualizar forma de pago",
#     description="Modifica configuración de una forma de pago existente."
# )
# async def update_forma_pago(
#     forma_pago_id: int,
#     forma_pago_in: FormaPagoUpdate,
#     current_user: Annotated[Usuario, Depends(lambda: require_role(["ADMIN"]))],
#     db: Annotated[Session, Depends(get_db)]
# ) -> FormaPagoPublic:
#     """
#     Permite activar/desactivar formas de pago sin eliminarlas
#     Modifica descripción y configuración
#     """
#     service = FormaPagoService(db)
#     return service.update_forma_pago(
#         forma_pago_id=forma_pago_id,
#         forma_pago_in=forma_pago_in,
#         es_admin=True
#     )
    
# @router.delete(
#     "/{forma_pago_id}",
#     status_code=status.HTTP_204_NO_CONTENT,
#     summary="[ADMIN] Eliminar forma de pago (soft delete)",
#     description="Desactiva lógicamente una forma de pago. No se elimina si hay pedidos asociados."
# )
# async def delete_forma_pago(
#     forma_pago_id: int,
#     current_user: Annotated[Usuario, Depends(lambda: require_role(["ADMIN"]))],
#     db: Annotated[Session, Depends(get_db)]
# ) -> None:
#     """
#     Marca is_active=False y deleted_at
#     Validar que no haya pedidos pendientes usando esta forma de pago
#     Permite mantener historial sin afectar reportes
#     """
#     service = FormaPagoService(db)
#     service.delete_forma_pago(
#         forma_pago_id=forma_pago_id,
#         es_admin=True
#     )
#     return None  

@router.get(
    "/",
    response_model=FormaPagoList,
    summary="Listar formas de pago",
)
def list_formas_pago(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    svc: FormaPagoService = Depends(get_forma_pago_service),
) -> FormaPagoList:
    return svc.get_all(offset=offset, limit=limit)