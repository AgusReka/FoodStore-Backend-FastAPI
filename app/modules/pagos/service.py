import json
from sqlmodel import Session
from typing import Optional, List
from fastapi import HTTPException, status
from app.modules.pagos.models import FormaPago, PagoMP
from app.modules.pagos.unit_of_work import PaymentUnitOfWork
from app.modules.pagos.schemas import (
    FormaPagoCreate,
    FormaPagoUpdate,
    FormaPagoList,
    CrearPreferenciaRequest,
    CrearPreferenciaResponse,
    ConfirmarPagoResponse,
)
from app.core.config import settings
from datetime import datetime, timezone
from decimal import Decimal
import uuid
import mercadopago

from app.modules.pedidos.models import Pedido, DetallePedido, HistorialEstadoPedido
from app.modules.pedidos.schemas import EstadoPedidoEnum, PedidoPublic
from app.core.websocket import manager

COSTO_ENVIO_DELIVERY = Decimal("500.00")


# ─── Helpers de notificación WebSocket (misma lógica que PedidoService) ────────

_ROLE_VISIBILITY: dict[str, set[EstadoPedidoEnum]] = {
    "ADMIN": {
        EstadoPedidoEnum.PENDIENTE,
        EstadoPedidoEnum.CONFIRMADO,
        EstadoPedidoEnum.EN_PREP,
        EstadoPedidoEnum.LISTO,
        EstadoPedidoEnum.CANCELADO,
        EstadoPedidoEnum.ENTREGADO,
    },
    "PEDIDOS": {
        EstadoPedidoEnum.PENDIENTE,
        EstadoPedidoEnum.CONFIRMADO,
        EstadoPedidoEnum.EN_PREP,
        EstadoPedidoEnum.LISTO,
        EstadoPedidoEnum.CANCELADO,
        EstadoPedidoEnum.ENTREGADO,
    },
    "COCINA": {EstadoPedidoEnum.CONFIRMADO, EstadoPedidoEnum.EN_PREP},
}


def _roles_que_ven(codigo: EstadoPedidoEnum) -> set[str]:
    return {rol for rol, estados in _ROLE_VISIBILITY.items() if codigo in estados}


def _build_notificaciones(
    pedido: Pedido,
    estado_nuevo_codigo: EstadoPedidoEnum,
    estado_anterior_codigo: Optional[EstadoPedidoEnum] = None,
) -> List[tuple]:
    """Prepara notificaciones WebSocket (misma lógica que PedidoService)."""
    data = PedidoPublic.model_validate(pedido).model_dump(mode="json")

    def msg(event: str) -> dict:
        return {"event": event, "id": pedido.id, "data": data}

    notifs: List[tuple] = []

    roles_nuevo = _roles_que_ven(estado_nuevo_codigo)
    if roles_nuevo:
        notifs.append(("roles", roles_nuevo, msg("UPSERT")))

    if estado_anterior_codigo is not None:
        roles_salientes = _roles_que_ven(estado_anterior_codigo) - roles_nuevo
        if roles_salientes:
            notifs.append(("roles", roles_salientes, msg("REMOVE")))

    notifs.append(("order", pedido.id, msg("PEDIDO_ESTADO")))
    return notifs


def _emit_notificaciones(notifs: List[tuple]) -> None:
    """Emitir notificaciones preparadas (fuera del UoW)."""
    for kind, target, msg in notifs:
        if kind == "roles":
            manager.notify_roles(target, msg)
        else:
            manager.notify(f"order:{target}", msg)


# ─── Servicios ─────────────────────────────────────────────────────────────────


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
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Forma de pago ID {forma_pago_id} no encontrada",
                )
            return forma_pago

    def create_forma_pago(self, forma_pago_in: FormaPagoCreate, es_admin: bool = True) -> FormaPago:
        if not es_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para crear formas de pago.",
            )
        with PaymentUnitOfWork(self._session) as uow:
            existing = uow.formas_pago.get_by_nombre(forma_pago_in.nombre)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe una forma de pago con el nombre '{forma_pago_in.nombre}'.",
                )
            forma_pago = FormaPago(**forma_pago_in.model_dump())
            return uow.formas_pago.create(forma_pago)

    def update_forma_pago(self, forma_pago_id: int, forma_pago_in: FormaPagoUpdate, es_admin: bool = True) -> FormaPago:
        if not es_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo administradores pueden modificar formas de pago",
            )
        with PaymentUnitOfWork(self._session) as uow:
            forma_pago = uow.formas_pago.get(forma_pago_id)
            if not forma_pago or forma_pago.deleted_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Forma de pago ID {forma_pago_id} no encontrada",
                )
            update_data = forma_pago_in.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if value is not None:
                    setattr(forma_pago, field, value)
            return uow.formas_pago.update(forma_pago_id, forma_pago)

    def delete_forma_pago(self, forma_pago_id: int, es_admin: bool = True) -> None:
        if not es_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo administradores pueden eliminar formas de pago",
            )
        with PaymentUnitOfWork(self._session) as uow:
            forma_pago = uow.formas_pago.get(forma_pago_id)
            if not forma_pago or forma_pago.deleted_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Forma de pago ID {forma_pago_id} no encontrada",
                )
            uow.formas_pago.delete(forma_pago_id)


class PaymentService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._sdk = mercadopago.SDK(settings.MP_ACCESS_TOKEN) if settings.MP_ACCESS_TOKEN else None

    def _check_sdk(self):
        if not self._sdk:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="MercadoPago no configurado",
            )

    def _mapear_estado_mp(self, mp_status: str) -> str:
        if mp_status == "approved":
            return "approved"
        if mp_status in ("rejected", "cancelled", "refunded"):
            return "rejected"
        return "pending"

    # ─── Crear preferencia (SIN pedido) ────────────────────────────────────

    def crear_preferencia(
        self, req: CrearPreferenciaRequest, usuario_id: int
    ) -> CrearPreferenciaResponse:
        self._check_sdk()

        with PaymentUnitOfWork(self._session) as uow:
            # 1. Validar productos y calcular total
            if not req.detalles:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Debe incluir al menos un producto",
                )

            subtotal = Decimal("0.00")
            mp_items = []
            for detalle_in in req.detalles:
                producto = uow.products.get_by_id(detalle_in.producto_id)
                if not producto:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Producto ID {detalle_in.producto_id} no encontrado",
                    )
                if not producto.available:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Producto '{producto.name}' no está disponible",
                    )

                # Validar stock para productos sin receta
                ingredient_links = uow.products.get_ingredient_links(producto.id)
                if not ingredient_links and producto.stock_quantity < detalle_in.cantidad:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=(
                            f"Stock insuficiente para '{producto.name}'. "
                            f"Disponible: {producto.stock_quantity}"
                        ),
                    )

                precio = producto.base_price
                subtotal += precio * detalle_in.cantidad

                mp_items.append({
                    "title": producto.name,
                    "quantity": detalle_in.cantidad,
                    "unit_price": float(precio),
                    "currency_id": "ARS",
                })

            # 2. Validar stock de ingredientes para productos compuestos
            ingredient_requirements: dict[int, int] = {}
            for detalle_in in req.detalles:
                links = uow.products.get_ingredient_links(detalle_in.producto_id)
                for link in links:
                    required = link.quantity * detalle_in.cantidad
                    ingredient_requirements[link.ingredient_id] = (
                        ingredient_requirements.get(link.ingredient_id, 0) + required
                    )

            if ingredient_requirements:
                ingredients = uow.ingredients.get_all_in(list(ingredient_requirements.keys()))
                missing = set(ingredient_requirements.keys()) - {ing.id for ing in ingredients}
                if missing:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Ingredientes no encontrados: {list(missing)}",
                    )
                for ing in ingredients:
                    required = ingredient_requirements[ing.id]
                    if ing.stock_quantity < required:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=(
                                f"Stock insuficiente para ingrediente '{ing.name}'. "
                                f"Requerido: {required}, disponible: {ing.stock_quantity}"
                            ),
                        )

            # 3. Calcular total
            costo_envio = COSTO_ENVIO_DELIVERY if req.tipo_envio == "delivery" else Decimal("0.00")
            total = subtotal + costo_envio

            # 4. Crear PagoMP (sin pedido_id)
            external_reference = str(uuid.uuid4())
            idempotency_key = str(uuid.uuid4())

            checkout_data = {
                "usuario_id": usuario_id,
                "items": [{"producto_id": d.producto_id, "cantidad": d.cantidad} for d in req.detalles],
                "direccion_entrega_id": req.direccion_entrega_id,
                "forma_pago_id": req.forma_pago_id,
                "tipo_envio": req.tipo_envio,
                "subtotal": str(subtotal),
                "costo_envio": str(costo_envio),
                "total": str(total),
            }

            pago_mp = PagoMP(
                mp_status="pending",
                transaction_amount=total,
                external_reference=external_reference,
                idempotency_key=idempotency_key,
                checkout_data=json.dumps(checkout_data),
            )
            uow.pagos_mp.create(pago_mp)

            # 5. Crear preferencia en MP
            base_redirect = settings.NGROK_URL or settings.VITE_FRONTEND_URL
            preference_data = {
                "items": mp_items,
                "external_reference": external_reference,
                "back_urls": {
                    "success": f"{base_redirect}/api/v1/pagos/redirect/success",
                    "failure": f"{base_redirect}/api/v1/pagos/redirect/cart",
                    "pending": f"{base_redirect}/api/v1/pagos/redirect/cart",
                },
                "auto_return": "approved",
                "notification_url": settings.MP_WEBHOOK_URL,
            }

            result = self._sdk.preference().create(preference_data)
            if result["status"] not in (200, 201):
                raise HTTPException(
                    status_code=status.HTTP_502_BAD_GATEWAY,
                    detail="Error al crear preferencia en MercadoPago",
                )

            response = result["response"]

            return CrearPreferenciaResponse(
                init_point=response["init_point"],
                preference_id=response["id"],
            )

    # ─── Confirmar pago (crea el pedido si está aprobado) ──────────────────

    def confirmar_pago(
        self, payment_id: int
    ) -> ConfirmarPagoResponse:
        self._check_sdk()

        # 1. Consultar MP
        mp_response = self._sdk.payment().get(payment_id)
        if mp_response["status"] != 200:
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail="Error al consultar el pago en MercadoPago",
            )

        mp_payment = mp_response["response"]
        mp_status = self._mapear_estado_mp(mp_payment.get("status", ""))
        external_ref = mp_payment.get("external_reference", "")

        if not external_ref:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="external_reference no encontrada en el pago",
            )

        # 2. Transacción: actualizar PagoMP + crear pedido si aprobado
        with PaymentUnitOfWork(self._session) as uow:
            pago_mp = uow.pagos_mp.get_by_external_reference(external_ref)
            if not pago_mp:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Transacción no encontrada",
                )

            # Idempotencia: si ya tiene pedido asociado, devolverlo
            if pago_mp.pedido_id is not None:
                return ConfirmarPagoResponse(
                    estado=pago_mp.mp_status,
                    pedido_id=pago_mp.pedido_id,
                )

            # Actualizar datos de MP
            pago_mp.mp_payment_id = payment_id
            pago_mp.mp_status = mp_status
            pago_mp.mp_status_detail = mp_payment.get("status_detail")
            pago_mp.updated_at = datetime.now(timezone.utc)
            uow.pagos_mp.update(pago_mp.id, pago_mp)

            if mp_status != "approved":
                return ConfirmarPagoResponse(
                    estado=mp_status,
                    pedido_id=None,
                )

            # 3. Pago aprobado → crear el pedido desde checkout_data
            checkout_data = json.loads(pago_mp.checkout_data)

            usuario_id = checkout_data["usuario_id"]
            tipo_envio = checkout_data["tipo_envio"]
            subtotal = Decimal(checkout_data["subtotal"])
            costo_envio = Decimal(checkout_data["costo_envio"])
            total = Decimal(checkout_data["total"])

            # Descontar stock
            for item in checkout_data["items"]:
                producto = uow.products.get_by_id(item["producto_id"])
                if not producto:
                    continue

                ingredient_links = uow.products.get_ingredient_links(producto.id)
                if ingredient_links:
                    for link in ingredient_links:
                        ing = uow.ingredients.get_by_id(link.ingredient_id)
                        if ing:
                            ing.stock_quantity -= link.quantity * item["cantidad"]
                            uow.ingredients.update(ing.id, ing)
                else:
                    producto.stock_quantity -= item["cantidad"]
                    if producto.stock_quantity == 0:
                        producto.available = False
                    uow.products.update(producto.id, producto)

            # Crear pedido como CONFIRMADO (el pago ya fue aprobado por MP)
            estado_confirmado = uow.estados.get_by_codigo(EstadoPedidoEnum.CONFIRMADO)
            pedido = Pedido(
                usuario_id=usuario_id,
                estado_id=estado_confirmado.id,
                direccion_entrega_id=checkout_data["direccion_entrega_id"],
                forma_pago_id=checkout_data["forma_pago_id"],
                subtotal=subtotal,
                costo_envio=costo_envio,
                total=total,
            )
            uow.pedidos.create(pedido)
            uow._session.flush()

            # Crear detalles
            for item in checkout_data["items"]:
                producto = uow.products.get_by_id(item["producto_id"])
                detalle = DetallePedido(
                    pedido_id=pedido.id,
                    producto_id=item["producto_id"],
                    producto_nombre=producto.name if producto else f"Producto #{item['producto_id']}",
                    producto_precio_unitario=producto.base_price if producto else Decimal("0"),
                    cantidad=item["cantidad"],
                    subtotal=(producto.base_price if producto else Decimal("0")) * item["cantidad"],
                )
                uow.detalles.create(detalle)

            # Registrar estado inicial como CONFIRMADO
            historial = HistorialEstadoPedido(
                pedido_id=pedido.id,
                estado_id=estado_confirmado.id,
                observaciones="Pedido creado desde pago MP confirmado",
            )
            uow.historial.create(historial)

            # Vincular PagoMP con el nuevo pedido
            pago_mp.pedido_id = pedido.id
            uow.pagos_mp.update(pago_mp.id, pago_mp)

            # Preparar notificaciones (dentro del UoW para serializar datos)
            notifs = _build_notificaciones(
                pedido,
                estado_nuevo_codigo=EstadoPedidoEnum.CONFIRMADO,
            )

        # Fuera del UoW → transacción commiteada, emitir notificaciones
        _emit_notificaciones(notifs)

        return ConfirmarPagoResponse(
            estado="approved",
            pedido_id=pedido.id,
        )

    # ─── Webhook de MP (misma lógica que confirm pero sin auth) ────────────

    def procesar_notificacion_pago(self, payment_id: int) -> dict:
        self._check_sdk()

        mp_response = self._sdk.payment().get(payment_id)
        if mp_response["status"] != 200:
            return {"status": "ok"}

        mp_payment = mp_response["response"]
        mp_status = self._mapear_estado_mp(mp_payment.get("status", ""))
        external_ref = mp_payment.get("external_reference", "")

        if not external_ref:
            return {"status": "ok"}

        with PaymentUnitOfWork(self._session) as uow:
            pago_mp = uow.pagos_mp.get_by_external_reference(external_ref)
            if not pago_mp:
                return {"status": "ok"}

            # Ya procesado
            if pago_mp.mp_payment_id and pago_mp.mp_status != "pending":
                return {"status": "ok"}

            # Ya tiene pedido → solo actualizar status
            if pago_mp.pedido_id is not None:
                pago_mp.mp_payment_id = payment_id
                pago_mp.mp_status = mp_status
                pago_mp.mp_status_detail = mp_payment.get("status_detail")
                pago_mp.updated_at = datetime.now(timezone.utc)
                uow.pagos_mp.update(pago_mp.id, pago_mp)
                return {"status": "ok"}

            # Actualizar datos de MP
            pago_mp.mp_payment_id = payment_id
            pago_mp.mp_status = mp_status
            pago_mp.mp_status_detail = mp_payment.get("status_detail")
            pago_mp.updated_at = datetime.now(timezone.utc)
            uow.pagos_mp.update(pago_mp.id, pago_mp)

            if mp_status != "approved":
                return {"status": "ok"}

            if not pago_mp.checkout_data:
                return {"status": "ok"}

            # Pago aprobado y sin pedido → crear el pedido
            checkout_data = json.loads(pago_mp.checkout_data)
            usuario_id = checkout_data["usuario_id"]
            tipo_envio = checkout_data["tipo_envio"]
            subtotal = Decimal(checkout_data["subtotal"])
            costo_envio = Decimal(checkout_data["costo_envio"])
            total = Decimal(checkout_data["total"])

            # Descontar stock
            for item in checkout_data["items"]:
                producto = uow.products.get_by_id(item["producto_id"])
                if not producto:
                    continue

                ingredient_links = uow.products.get_ingredient_links(producto.id)
                if ingredient_links:
                    for link in ingredient_links:
                        ing = uow.ingredients.get_by_id(link.ingredient_id)
                        if ing:
                            ing.stock_quantity -= link.quantity * item["cantidad"]
                            uow.ingredients.update(ing.id, ing)
                else:
                    producto.stock_quantity -= item["cantidad"]
                    if producto.stock_quantity == 0:
                        producto.available = False
                    uow.products.update(producto.id, producto)

            # Crear pedido como CONFIRMADO (el pago ya fue aprobado por MP)
            estado_confirmado = uow.estados.get_by_codigo(EstadoPedidoEnum.CONFIRMADO)
            pedido = Pedido(
                usuario_id=usuario_id,
                estado_id=estado_confirmado.id,
                direccion_entrega_id=checkout_data["direccion_entrega_id"],
                forma_pago_id=checkout_data["forma_pago_id"],
                subtotal=subtotal,
                costo_envio=costo_envio,
                total=total,
            )
            uow.pedidos.create(pedido)
            uow._session.flush()

            for item in checkout_data["items"]:
                producto = uow.products.get_by_id(item["producto_id"])
                detalle = DetallePedido(
                    pedido_id=pedido.id,
                    producto_id=item["producto_id"],
                    producto_nombre=producto.name if producto else f"Producto #{item['producto_id']}",
                    producto_precio_unitario=producto.base_price if producto else Decimal("0"),
                    cantidad=item["cantidad"],
                    subtotal=(producto.base_price if producto else Decimal("0")) * item["cantidad"],
                )
                uow.detalles.create(detalle)

            historial = HistorialEstadoPedido(
                pedido_id=pedido.id,
                estado_id=estado_confirmado.id,
                observaciones="Pedido creado desde webhook MP",
            )
            uow.historial.create(historial)

            pago_mp.pedido_id = pedido.id
            uow.pagos_mp.update(pago_mp.id, pago_mp)

            notifs = _build_notificaciones(
                pedido,
                estado_nuevo_codigo=EstadoPedidoEnum.CONFIRMADO,
            )

        _emit_notificaciones(notifs)
        return {"status": "ok"}
