from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Annotated, Optional, List
from sqlmodel import Session
from app.core.database import get_session
from app.modules.pagos.service import FormaPagoService
from app.modules.pagos.schemas import (
    FormaPagoCreate,
    FormaPagoUpdate,
    FormaPagoPublic,
    FormaPagoList
)

router = APIRouter(
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

@router.get(
    "/",
    response_model=FormaPagoList,
    summary="Listar formas de pago disponibles",
    description="Obtiene todas las formas de pago registradas con paginación."
)
def list_formas_pago(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    svc: FormaPagoService = Depends(get_forma_pago_service),
) -> FormaPagoList:
    return svc.get_all(offset=offset, limit=limit)

@router.get(
    "/{forma_pago_id}",
    response_model=FormaPagoPublic,
    summary="Obtener forma de pago por ID",
    description="Obtiene los detalles de una forma de pago específica."
)
def get_forma_pago(
    forma_pago_id: int,
    svc: FormaPagoService = Depends(get_forma_pago_service)
) -> FormaPagoPublic:
    """Consulta pública de una forma de pago por ID."""
    return svc.get_forma_pago_by_id(forma_pago_id)

@router.post(
    "/",
    response_model=FormaPagoPublic,
    status_code=status.HTTP_201_CREATED,
    summary="[ADMIN] Crear forma de pago",
    description="Agrega una nueva forma de pago al sistema (simula permisos de ADMIN)."
)
def create_forma_pago(
    forma_pago_in: FormaPagoCreate,
    svc: FormaPagoService = Depends(get_forma_pago_service),
    es_admin: bool = Query(default=True, description="Simular si es administrador")
) -> FormaPagoPublic:
    """
    Simula rol ADMIN por defecto.
    Valida unicidad del nombre.
    """
    return svc.create_forma_pago(
        forma_pago_in=forma_pago_in,
        es_admin=es_admin
    )
    
@router.patch(
    "/{forma_pago_id}",
    response_model=FormaPagoPublic,
    summary="[ADMIN] Actualizar forma de pago",
    description="Modifica la configuración de una forma de pago existente."
)
def update_forma_pago(
    forma_pago_id: int,
    forma_pago_in: FormaPagoUpdate,
    svc: FormaPagoService = Depends(get_forma_pago_service),
    es_admin: bool = Query(default=True, description="Simular si es administrador")
) -> FormaPagoPublic:
    """Modifica descripción y configuración."""
    return svc.update_forma_pago(
        forma_pago_id=forma_pago_id,
        forma_pago_in=forma_pago_in,
        es_admin=es_admin
    )
    
@router.delete(
    "/{forma_pago_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[ADMIN] Eliminar forma de pago (soft delete)",
    description="Desactiva lógicamente una forma de pago."
)
def delete_forma_pago(
    forma_pago_id: int,
    svc: FormaPagoService = Depends(get_forma_pago_service),
    es_admin: bool = Query(default=True, description="Simular si es administrador")
) -> None:
    svc.delete_forma_pago(
        forma_pago_id=forma_pago_id,
        es_admin=es_admin
    )
    return None