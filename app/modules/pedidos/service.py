from sqlmodel import Session
from typing import List, Optional
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException, status
from app.modules.pedidos.unit_of_work import OrderUnitOfWork
from app.modules.pedidos.models import (
    Pedido,
    DetallePedido,
    HistorialEstadoPedido,
    EstadoPedidoEnum,
)
from app.modules.pedidos.schemas import (
    PedidoCreate,
    PedidoUpdate,
    CambioEstadoRequest,
)
from app.modules.product.repository import ProductRepository


class PedidoService:
    def __init__(self, session: Session) -> None:
        self._session = session


    def crear_pedido(self, usuario_id: int, pedido_in: PedidoCreate) -> Pedido:
        with OrderUnitOfWork(self._session) as uow:
            if not pedido_in.detalles:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El pedido debe contener al menos un producto",
                )

            product_repo = ProductRepository(self._session)
            subtotal = Decimal("0.00")
            detalles_a_crear = []

            for detalle_in in pedido_in.detalles:
                producto = product_repo.get_by_id(detalle_in.producto_id)

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
                if producto.stock_quantity < detalle_in.cantidad:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Stock insuficiente para '{producto.name}'. Disponible: {producto.stock_quantity}",
                    )

                precio_unitario = producto.base_price
                subtotal_detalle = precio_unitario * detalle_in.cantidad
                subtotal += subtotal_detalle

                detalles_a_crear.append({
                    "producto_id": detalle_in.producto_id,
                    "producto_nombre": producto.name,
                    "producto_precio_unitario": precio_unitario,
                    "cantidad": detalle_in.cantidad,
                    "subtotal": subtotal_detalle,
                })

                producto.stock_quantity -= detalle_in.cantidad
                if producto.stock_quantity == 0:
                    producto.available = False
                product_repo.update(producto.id, producto)

            costo_envio = Decimal("0.00")
            total = subtotal + costo_envio

            pedido_data = pedido_in.model_dump(exclude={"detalles"})
            pedido = Pedido(
                **pedido_data,
                usuario_id=usuario_id,
                estado_id=1,
                subtotal=subtotal,
                costo_envio=costo_envio,
                total=total,
            )
            uow.pedidos.create(pedido)
            self._session.flush()

            for detalle_data in detalles_a_crear:
                detalle = DetallePedido(pedido_id=pedido.id, **detalle_data)
                uow.detalles.create(detalle)

            self._registrar_cambio_estado(
                uow,
                pedido_id=pedido.id,
                nuevo_estado=EstadoPedidoEnum.PENDIENTE,
                observaciones="Pedido creado exitosamente",
            )

            return pedido


    def get_pedido_by_id(
        self, pedido_id: int, usuario_id: Optional[int] = None, es_admin: bool = False
    ) -> Pedido:
        with OrderUnitOfWork(self._session) as uow:
            pedido = uow.pedidos.get(pedido_id)
            if not pedido or pedido.deleted_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Pedido no encontrado",
                )
            if usuario_id is not None and not es_admin:
                if pedido.usuario_id != usuario_id:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="No tienes permiso para ver este pedido",
                    )
            return pedido

    def get_pedidos_by_usuario(
        self, usuario_id: int, offset: int = 0, limit: int = 20
    ) -> List[Pedido]:
        with OrderUnitOfWork(self._session) as uow:
            return uow.pedidos.get_by_usuario_id(usuario_id, offset, limit)

    def get_all_pedidos_admin(
        self,
        estado_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> List[Pedido]:
        with OrderUnitOfWork(self._session) as uow:
            return uow.pedidos.get_all_admin(estado_id, offset, limit)


    TRANSICIONES_VALIDAS = {
        EstadoPedidoEnum.PENDIENTE: [EstadoPedidoEnum.CONFIRMADO, EstadoPedidoEnum.CANCELADO],
        EstadoPedidoEnum.CONFIRMADO: [EstadoPedidoEnum.EN_PREP, EstadoPedidoEnum.CANCELADO],
        EstadoPedidoEnum.EN_PREP: [EstadoPedidoEnum.EN_CAMINO],
        EstadoPedidoEnum.EN_CAMINO: [EstadoPedidoEnum.ENTREGADO],
        EstadoPedidoEnum.ENTREGADO: [],
        EstadoPedidoEnum.CANCELADO: [],
    }

    def cambiar_estado_pedido(
        self,
        pedido_id: int,
        cambio: CambioEstadoRequest,
        usuario_cambio_id: Optional[int] = None,
    ) -> Pedido:
        with OrderUnitOfWork(self._session) as uow:
            pedido = uow.pedidos.get(pedido_id)
            if not pedido or pedido.deleted_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Pedido no encontrado",
                )

            estado_actual = uow.estados.get(pedido.estado_id)
            nuevo_estado = uow.estados.get_by_codigo(cambio.nuevo_estado)

            if not nuevo_estado:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Estado '{cambio.nuevo_estado.value}' no existe",
                )

            if nuevo_estado.codigo not in self.TRANSICIONES_VALIDAS.get(estado_actual.codigo, []):
                permitidos = [e.value for e in self.TRANSICIONES_VALIDAS.get(estado_actual.codigo, [])]
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Transición inválida: de '{estado_actual.codigo.value}' "
                        f"no se puede ir a '{nuevo_estado.codigo.value}'. "
                        f"Estados permitidos: {permitidos}"
                    ),
                )

            pedido.estado_id = nuevo_estado.id
            pedido.updated_at = datetime.now(timezone.utc)
            uow.pedidos.update(pedido.id, pedido)

            self._registrar_cambio_estado(
                uow,
                pedido_id=pedido.id,
                nuevo_estado=cambio.nuevo_estado,
                usuario_cambio_id=usuario_cambio_id,
                observaciones=cambio.observaciones,
            )

            return pedido

    def cancelar_pedido(self, pedido_id: int, usuario_id: int) -> Pedido:
        with OrderUnitOfWork(self._session) as uow:
            pedido = uow.pedidos.get(pedido_id)
            if not pedido or pedido.deleted_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Pedido no encontrado",
                )
            if pedido.usuario_id != usuario_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permiso para cancelar este pedido",
                )

            estado_actual = uow.estados.get(pedido.estado_id)
            cancelables = [EstadoPedidoEnum.PENDIENTE, EstadoPedidoEnum.CONFIRMADO]
            if estado_actual.codigo not in cancelables:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"El pedido no puede cancelarse desde el estado '{estado_actual.codigo.value}'",
                )

            nuevo_estado = uow.estados.get_by_codigo(EstadoPedidoEnum.CANCELADO)
            pedido.estado_id = nuevo_estado.id
            pedido.updated_at = datetime.now(timezone.utc)
            uow.pedidos.update(pedido.id, pedido)

            # Reintegrar stock automáticamente
            product_repo = ProductRepository(self._session)
            for detalle in pedido.detalles:
                producto = product_repo.get_by_id(detalle.producto_id)
                if producto:
                    producto.stock_quantity += detalle.cantidad
                    if not producto.available and producto.stock_quantity > 0:
                        producto.available = True
                    product_repo.update(producto.id, producto)

            self._registrar_cambio_estado(
                uow,
                pedido_id=pedido.id,
                nuevo_estado=EstadoPedidoEnum.CANCELADO,
                usuario_cambio_id=usuario_id,
                observaciones="Cancelado por el cliente",
            )

            return pedido

    def update_pedido(self, pedido_id: int, pedido_in: PedidoUpdate, usuario_id: int) -> Pedido:
        with OrderUnitOfWork(self._session) as uow:
            pedido = uow.pedidos.get(pedido_id)
            if not pedido or pedido.deleted_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Pedido no encontrado",
                )
            if pedido.usuario_id != usuario_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permiso para modificar este pedido",
                )

            estado_actual = uow.estados.get(pedido.estado_id)
            if estado_actual.orden >= 3:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="No se puede modificar un pedido que ya está en preparación",
                )

            update_data = pedido_in.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if value is not None:
                    setattr(pedido, field, value)
            pedido.updated_at = datetime.now(timezone.utc)
            uow.pedidos.update(pedido.id, pedido)
            return pedido


    def _registrar_cambio_estado(
        self,
        uow: OrderUnitOfWork,
        pedido_id: int,
        nuevo_estado: EstadoPedidoEnum,
        usuario_cambio_id: Optional[int] = None,
        observaciones: Optional[str] = None,
    ) -> None:
        estado = uow.estados.get_by_codigo(nuevo_estado)
        historial = HistorialEstadoPedido(
            pedido_id=pedido_id,
            estado_id=estado.id,
            usuario_cambio_id=usuario_cambio_id,
            observaciones=observaciones,
        )
        uow.historial.create(historial)

    def count_pedidos_by_usuario(self, usuario_id: int) -> int:
        with OrderUnitOfWork(self._session) as uow:
            return uow.pedidos.count_by_usuario(usuario_id)

    def count_pedidos_admin(self, estado_id: Optional[int] = None) -> int:
        with OrderUnitOfWork(self._session) as uow:
            return uow.pedidos.count_admin(estado_id)

    def get_estados_pedido_ordered(self):
        with OrderUnitOfWork(self._session) as uow:
            return uow.estados.get_all_ordered()

    def get_historial_estados(self, pedido_id: int) -> List[HistorialEstadoPedido]:
        with OrderUnitOfWork(self._session) as uow:
            return uow.historial.get_by_pedido_id(pedido_id)
