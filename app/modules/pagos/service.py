from sqlmodel import Session
from typing import Optional
from app.core.exceptions.custom_exceptions import (
    AppError,
    AuthorizationError,
    DuplicateResourceError,
    ResourceNotFoundError,
)
from app.modules.pagos.models import FormaPago, PagoMP
from app.modules.pagos.unit_of_work import PaymentUnitOfWork
from app.modules.pagos.schemas import (
    FormaPagoCreate,
    FormaPagoUpdate,
    FormaPagoList,
    CrearPreferenciaResponse,
    PagoMPStatusResponse,
)
from app.core.config import settings
from datetime import datetime, timezone
from decimal import Decimal
import uuid
import mercadopago


class FormaPagoService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_all(self, offset: int = 0, limit: int = 20, include_deleted: bool = False) -> FormaPagoList:
        with PaymentUnitOfWork(self._session) as uow:
            formas_pago = list(uow.formas_pago.get_all(offset=offset, limit=limit, include_deleted=include_deleted))
            total = uow.formas_pago.count(include_deleted=include_deleted)
            return FormaPagoList(data=formas_pago, total=total)

    def get_forma_pago_by_id(self, forma_pago_id: int) -> FormaPago:
        with PaymentUnitOfWork(self._session) as uow:
            forma_pago = uow.formas_pago.get(forma_pago_id)
            if not forma_pago or forma_pago.deleted_at is not None:
                raise ResourceNotFoundError(
                    message=f"Forma de pago ID {forma_pago_id} no encontrada"
                )
            return forma_pago

    def create_forma_pago(self, forma_pago_in: FormaPagoCreate, es_admin: bool = True) -> FormaPago:
        if not es_admin:
            raise AuthorizationError(message="No tienes permisos para crear formas de pago.")
        with PaymentUnitOfWork(self._session) as uow:
            existing = uow.formas_pago.get_by_nombre(forma_pago_in.nombre)
            if existing:
                raise DuplicateResourceError(
                    message=f"Ya existe una forma de pago con el nombre '{forma_pago_in.nombre}'."
                )
            forma_pago = FormaPago(**forma_pago_in.model_dump())
            return uow.formas_pago.create(forma_pago)

    def update_forma_pago(self, forma_pago_id: int, forma_pago_in: FormaPagoUpdate, es_admin: bool = True) -> FormaPago:
        if not es_admin:
            raise AuthorizationError(message="Solo administradores pueden modificar formas de pago")
        with PaymentUnitOfWork(self._session) as uow:
            forma_pago = uow.formas_pago.get(forma_pago_id)
            if not forma_pago or forma_pago.deleted_at is not None:
                raise ResourceNotFoundError(
                    message=f"Forma de pago ID {forma_pago_id} no encontrada"
                )
            update_data = forma_pago_in.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if value is not None:
                    setattr(forma_pago, field, value)
            return uow.formas_pago.update(forma_pago_id, forma_pago)

    def delete_forma_pago(self, forma_pago_id: int, es_admin: bool = True) -> None:
        if not es_admin:
            raise AuthorizationError(message="Solo administradores pueden eliminar formas de pago")
        with PaymentUnitOfWork(self._session) as uow:
            forma_pago = uow.formas_pago.get(forma_pago_id)
            if not forma_pago or forma_pago.deleted_at is not None:
                raise ResourceNotFoundError(
                    message=f"Forma de pago ID {forma_pago_id} no encontrada"
                )
            uow.formas_pago.delete(forma_pago_id)


class PaymentService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN) if settings.MP_ACCESS_TOKEN else None

    def _check_sdk(self):
        if not self._sdk:
            raise AppError(
                message="MercadoPago no configurado",
                status_code=500,
                code="mp_not_configured",
            )

    def _mapear_estado_mp(self, mp_status: str) -> str:
        if mp_status == "approved":
            return "approved"
        if mp_status == "rejected" or mp_status == "cancelled" or mp_status == "refunded":
            return "rejected"
        return "pending"

    def _actualizar_pedido_si_aprobado(self, pedido_id: int, uow: PaymentUnitOfWork) -> None:
        pedido = uow.pedidos.get(pedido_id)
        if pedido and pedido.estado_id == 1:
            pedido.estado_id = 2
            pedido.updated_at = datetime.now(timezone.utc)
            uow.pedidos.update(pedido.id, pedido)

    def crear_preferencia(self, pedido_id: int, usuario_id: int) -> CrearPreferenciaResponse:
        self._check_sdk()

        with PaymentUnitOfWork(self._session) as uow:
            pedido = uow.pedidos.get(pedido_id)
            if not pedido:
                raise ResourceNotFoundError(message="Pedido no encontrado")
            if pedido.usuario_id != usuario_id:
                raise AuthorizationError(message="No tienes acceso a este pedido")

            pago_mp = PagoMP(
                pedido_id=pedido_id,
                mp_status="pending",
                transaction_amount=pedido.total,
                external_reference=str(uuid.uuid4()),
                idempotency_key=str(uuid.uuid4()),
            )
            uow.pagos_mp.create(pago_mp)

            items = []
            for detalle in pedido.detalles:
                items.append({
                    "title": detalle.producto_nombre,
                    "quantity": detalle.cantidad,
                    "unit_price": float(detalle.producto_precio_unitario),
                    "currency_id": "ARS",
                })

            base_redirect = settings.NGROK_URL or settings.VITE_FRONTEND_URL
            preference_data = {
                "items": items,
                "external_reference": pago_mp.external_reference,
                "back_urls": {
                    "success": f"{base_redirect}/api/v1/pagos/redirect/{pedido_id}/success",
                    "failure": f"{base_redirect}/api/v1/pagos/redirect/{pedido_id}/failure",
                    "pending": f"{base_redirect}/api/v1/pagos/redirect/{pedido_id}/pending",
                },
                "auto_return": "approved",
                "notification_url": settings.MP_WEBHOOK_URL,
            }

            result = self._sdk.preference().create(preference_data)
            if result["status"] not in (200, 201):
                raise AppError(
                    message="Error al crear preferencia en MercadoPago",
                    status_code=502,
                    code="mp_bad_gateway",
                )

            response = result["response"]

            return CrearPreferenciaResponse(
                init_point=response["init_point"],
                preference_id=response["id"],
            )

    def confirmar_pago(
        self, pedido_id: int, payment_id: Optional[int] = None
    ) -> PagoMPStatusResponse:
        self._check_sdk()

        with PaymentUnitOfWork(self._session) as uow:
            if payment_id:
                pago_mp = uow.pagos_mp.get_by_mp_payment_id(payment_id)
            else:
                pago_mp = uow.pagos_mp.get_latest_by_pedido(pedido_id)

            if not pago_mp:
                raise ResourceNotFoundError(message="No se encontró pago asociado")

            mp_id = payment_id or pago_mp.mp_payment_id
            if mp_id:
                mp_response = self._sdk.payment().get(mp_id)
                if mp_response["status"] == 200:
                    mp_payment = mp_response["response"]
                    pago_mp.mp_payment_id = mp_payment.get("id")
                    pago_mp.mp_status = self._mapear_estado_mp(mp_payment.get("status", ""))
                    pago_mp.mp_status_detail = mp_payment.get("status_detail")
                    pago_mp.updated_at = datetime.now(timezone.utc)
                    uow.pagos_mp.update(pago_mp.id, pago_mp)

            if pago_mp.mp_status == "approved":
                self._actualizar_pedido_si_aprobado(pedido_id, uow)

            return PagoMPStatusResponse(
                estado=pago_mp.mp_status,
                pedido_id=pago_mp.pedido_id,
            )

    def procesar_notificacion_pago(self, payment_id: int) -> dict:
        self._check_sdk()

        with PaymentUnitOfWork(self._session) as uow:
            mp_response = self._sdk.payment().get(payment_id)
            if mp_response["status"] != 200:
                return {"status": "ok"}

            mp_payment = mp_response["response"]
            external_ref = mp_payment.get("external_reference", "")

            pago_mp = uow.pagos_mp.get_by_mp_payment_id(payment_id)
            if not pago_mp and external_ref:
                pago_mp = uow.pagos_mp.get_by_external_reference(external_ref)

            if not pago_mp:
                return {"status": "ok"}

            if pago_mp.mp_payment_id and pago_mp.mp_status != "pending":
                return {"status": "ok"}

            pago_mp.mp_payment_id = payment_id
            pago_mp.mp_status = self._mapear_estado_mp(mp_payment.get("status", ""))
            pago_mp.mp_status_detail = mp_payment.get("status_detail")
            pago_mp.updated_at = datetime.now(timezone.utc)
            uow.pagos_mp.update(pago_mp.id, pago_mp)

            if pago_mp.mp_status == "approved":
                self._actualizar_pedido_si_aprobado(pago_mp.pedido_id, uow)

            return {"status": "ok"}
