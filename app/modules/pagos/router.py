from fastapi import APIRouter, Depends, status, Query, Request
from fastapi.responses import RedirectResponse
from typing import Annotated
from sqlmodel import Session
from app.core.database import get_session
from app.core.deps import get_current_active_user, require_admin
from app.core.config import settings
from app.modules.user.models import User
from app.modules.pagos.service import FormaPagoService, PaymentService
from app.modules.pagos.schemas import (
    FormaPagoCreate,
    FormaPagoUpdate,
    FormaPagoPublic,
    FormaPagoList,
    CrearPreferenciaRequest,
    CrearPreferenciaResponse,
    ConfirmarPagoRequest,
    PagoMPStatusResponse,
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

def get_payment_service(session: Session = Depends(get_session)) -> PaymentService:
    """Factory de dependencia: inyecta el servicio de MercadoPago con su Session."""
    return PaymentService(session)

@router.get(
    "/",
    response_model=FormaPagoList,
    summary="Listar formas de pago disponibles",
    description="Obtiene todas las formas de pago registradas con paginación."
)
def list_formas_pago(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    include_deleted: bool = Query(default=False, description="Incluir registros eliminados (solo admin)"),
    svc: FormaPagoService = Depends(get_forma_pago_service),
) -> FormaPagoList:
    return svc.get_all(offset=offset, limit=limit, include_deleted=include_deleted)

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
    description="Agrega una nueva forma de pago al sistema."
)
def create_forma_pago(
    forma_pago_in: FormaPagoCreate,
    _: Annotated[User, Depends(require_admin)],
    svc: FormaPagoService = Depends(get_forma_pago_service)
) -> FormaPagoPublic:
    """
    Solo administradores pueden crear formas de pago.
    Valida unicidad del nombre.
    """
    return svc.create_forma_pago(
        forma_pago_in=forma_pago_in,
        es_admin=True
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
    _: Annotated[User, Depends(require_admin)],
    svc: FormaPagoService = Depends(get_forma_pago_service)
) -> FormaPagoPublic:
    """Solo administradores pueden modificar formas de pago."""
    return svc.update_forma_pago(
        forma_pago_id=forma_pago_id,
        forma_pago_in=forma_pago_in,
        es_admin=True
    )
    
@router.delete(
    "/{forma_pago_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="[ADMIN] Eliminar forma de pago (soft delete)",
    description="Desactiva lógicamente una forma de pago."
)
def delete_forma_pago(
    forma_pago_id: int,
    _: Annotated[User, Depends(require_admin)],
    svc: FormaPagoService = Depends(get_forma_pago_service)
) -> None:
    """Solo administradores pueden eliminar formas de pago."""
    svc.delete_forma_pago(
        forma_pago_id=forma_pago_id,
        es_admin=True
    )
    return None


@router.post(
    "/create-preference",
    response_model=CrearPreferenciaResponse,
    summary="Crear preferencia de pago en MercadoPago",
    description="Crea una preferencia de pago para un pedido específico."
)
def create_preference(
    req: CrearPreferenciaRequest,
    current_user: Annotated[User, Depends(get_current_active_user)],
    svc: PaymentService = Depends(get_payment_service)
) -> CrearPreferenciaResponse:
    return svc.crear_preferencia(
        pedido_id=req.pedido_id,
        usuario_id=current_user.id,
    )


@router.post(
    "/webhook",
    summary="Webhook de MercadoPago",
    description="Endpoint para notificaciones de pago de MercadoPago. Sin autenticación."
)
async def mercadopago_webhook(
    request: Request,
    svc: PaymentService = Depends(get_payment_service)
) -> dict:
    try:
        body = await request.json()
        data = body.get("data", {})
        payment_id = data.get("id")
    except Exception:
        try:
            form = await request.form()
            payment_id = form.get("id")
        except Exception:
            payment_id = None

    if payment_id:
        try:
            svc.procesar_notificacion_pago(payment_id=int(payment_id))
        except Exception:
            pass

    return {"status": "ok"}


@router.post(
    "/confirm",
    response_model=PagoMPStatusResponse,
    summary="Confirmar pago manualmente",
    description="Verifica el estado de un pago contra MercadoPago y actualiza el pedido."
)
def confirm_payment(
    req: ConfirmarPagoRequest,
    svc: PaymentService = Depends(get_payment_service)
) -> PagoMPStatusResponse:
    return svc.confirmar_pago(
        pedido_id=req.pedido_id,
        payment_id=req.payment_id,
    )


STATUS_MAP = {
    "success": "success",
    "failure": "failure",
    "approved": "success",
    "rejected": "failure",
    "pending": "success",
}

@router.get(
    "/redirect/{pedido_id}/{status}",
    summary="Redirección post-pago",
    description="Redirige al frontend después de un pago en MercadoPago."
)
def redirect_after_payment(
    pedido_id: int,
    status: str,
    request: Request = None,
):
    frontend_status = STATUS_MAP.get(status, "success")
    url = f"{settings.VITE_FRONTEND_URL}/orders/{pedido_id}/{frontend_status}"
    if request and request.query_params:
        qs = "&".join(
            f"{k}={v}" for k, v in request.query_params.items()
            if k not in ("pedido_id", "status")
        )
        if qs:
            url += f"?{qs}"
    return RedirectResponse(url=url)