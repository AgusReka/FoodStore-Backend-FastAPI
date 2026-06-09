from sqlmodel import Session
from typing import List, Optional
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from fastapi import HTTPException, status
from app.modules.pedidos.unit_of_work import OrderUnitOfWork
from app.modules.pedidos.models import (
    Pedido,
    DetallePedido,
    HistorialEstadoPedido,
)
from app.modules.pedidos.schemas import (
    PedidoCreate,
    PedidoUpdate,
    PedidoPublic,
    PedidoList,
    CambioEstadoRequest,
    EstadoPedidoEnum,
)
from app.modules.product.models import Product
from app.modules.product.repository import ProductRepository
from app.modules.ingredient.repository import IngredientRepository
from app.core.roles import RoleCode
from app.core.websocket import manager


# ─── Visibilidad por rol ──────────────────────────────────────────────────────
# Qué estados quiere VER cada rol staff (distinto de qué puede *operar*, que se
# valida con la tabla `transicion_estado`). Alimenta tanto la carga inicial
# (`/cola`) como el ruteo de notificaciones del WebSocket, para que el front
# ubique cada pedido por `estado_codigo` en la sección correcta.
_E = EstadoPedidoEnum

# Estados terminales: solo se muestran acotados a las últimas 24h en la carga
# inicial (en el WS, la transición terminal recién ocurrida siempre es reciente).
ESTADOS_TERMINALES: set[EstadoPedidoEnum] = {_E.CANCELADO, _E.ENTREGADO}

ROLE_VISIBILITY: dict[str, set[EstadoPedidoEnum]] = {
    RoleCode.PEDIDOS: {_E.PENDIENTE, _E.CONFIRMADO, _E.EN_PREP, _E.LISTO, _E.CANCELADO, _E.ENTREGADO},
    RoleCode.COCINA: {_E.CONFIRMADO, _E.EN_PREP},
    RoleCode.ADMIN: {_E.PENDIENTE, _E.CONFIRMADO, _E.EN_PREP, _E.LISTO, _E.CANCELADO, _E.ENTREGADO},
}


def roles_que_ven(codigo: EstadoPedidoEnum) -> set[str]:
    """Roles cuyo tablero incluye `codigo` (a quién notificar/UPSERT)."""
    return {rol for rol, estados in ROLE_VISIBILITY.items() if codigo in estados}


def estados_visibles(roles: List[str]) -> set[EstadoPedidoEnum]:
    """Unión de estados visibles para los roles dados (tablero del usuario)."""
    visibles: set[EstadoPedidoEnum] = set()
    for rol in roles:
        visibles |= ROLE_VISIBILITY.get(rol, set())
    return visibles


class PedidoService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _build_notificaciones(
        self,
        pedido: Pedido,
        estado_nuevo_codigo: EstadoPedidoEnum,
        estado_anterior_codigo: Optional[EstadoPedidoEnum] = None,
    ) -> List[tuple]:
        """Prepara las notificaciones WebSocket SIN emitirlas todavía.

        Debe llamarse DENTRO del bloque UoW (sesión viva): serializa el pedido a
        `PedidoPublic` para evitar `DetachedInstanceError` y forzar el lazy-load
        de `detalles`/`estado_actual`. El payload queda materializado para
        emitirse luego del commit (ver `_emit_notificaciones`), evitando avisar
        sobre datos no commiteados.

        El ruteo es por **visibilidad** (`ROLE_VISIBILITY`), no por operabilidad:
        un rol recibe el pedido si su tablero incluye el estado correspondiente.
        Todos los mensajes comparten el shape `{event, id, data}` con el
        `PedidoPublic` completo en `data`, para que el front mantenga sus listas
        por `id`:
        - Roles que ven el estado NUEVO reciben `UPSERT` (agregar/actualizar).
        - Roles que veían el estado anterior (y ya no el nuevo) reciben `REMOVE`.
        - El cliente dueño suscripto a `order:{id}` recibe `PEDIDO_ESTADO`.

        Devuelve una lista de tuplas `("roles", roles, msg)` / `("order", id, msg)`.
        """
        data = PedidoPublic.model_validate(pedido).model_dump(mode="json")

        def msg(event: str) -> dict:
            return {"event": event, "id": pedido.id, "data": data}

        notifs: List[tuple] = []

        roles_nuevo = roles_que_ven(estado_nuevo_codigo)
        if roles_nuevo:
            notifs.append(("roles", roles_nuevo, msg("UPSERT")))

        if estado_anterior_codigo is not None:
            roles_salientes = roles_que_ven(estado_anterior_codigo) - roles_nuevo
            if roles_salientes:
                notifs.append(("roles", roles_salientes, msg("REMOVE")))

        notifs.append(("order", pedido.id, msg("PEDIDO_ESTADO")))
        return notifs

    def _emit_notificaciones(self, notifs: List[tuple]) -> None:
        """Emite las notificaciones preparadas. Llamar DESPUÉS del commit."""
        for kind, target, msg in notifs:
            if kind == "roles":
                manager.notify_roles(target, msg)
            else:
                manager.notify(f"order:{target}", msg)

    def crear_pedido(self, usuario_id: int, pedido_in: PedidoCreate) -> Pedido:
        with OrderUnitOfWork(self._session) as uow:
            if not pedido_in.detalles:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="El pedido debe contener al menos un producto",
                )

            product_repo = ProductRepository(self._session)
            ingredient_repo = IngredientRepository(self._session)
            subtotal = Decimal("0.00")
            detalles_a_crear = []
            # Ingredientes necesarios para los productos compuestos
            ingredient_requirements: dict[int, int] = {}
            # Productos sin receta que usan su propio stock
            standalone_products: list[tuple[Product, int]] = []

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

                ingredient_links = product_repo.get_ingredient_links(producto.id)
                if ingredient_links:
                    # El producto usa ingredientes: acumular lo que hace falta
                    for link in ingredient_links:
                        required = link.quantity * detalle_in.cantidad
                        ingredient_requirements[link.ingredient_id] = (
                            ingredient_requirements.get(link.ingredient_id, 0)
                            + required
                        )
                else:
                    # Producto independiente: se descuenta directamente del stock del producto
                    if producto.stock_quantity < detalle_in.cantidad:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=(
                                f"Stock insuficiente para '{producto.name}'. "
                                f"Disponible: {producto.stock_quantity}"
                            ),
                        )
                    standalone_products.append((producto, detalle_in.cantidad))

                precio_unitario = producto.base_price
                subtotal_detalle = precio_unitario * detalle_in.cantidad
                subtotal += subtotal_detalle

                detalles_a_crear.append(
                    {
                        "producto_id": detalle_in.producto_id,
                        "producto_nombre": producto.name,
                        "producto_precio_unitario": precio_unitario,
                        "cantidad": detalle_in.cantidad,
                        "subtotal": subtotal_detalle,
                    }
                )

            if ingredient_requirements:
                required_ingredient_ids = list(ingredient_requirements.keys())
                ingredients = ingredient_repo.get_all_in(required_ingredient_ids)
                missing_ingredients = set(required_ingredient_ids) - {
                    ing.id for ing in ingredients
                }
                if missing_ingredients:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail=f"Ingredientes no encontrados: {list(missing_ingredients)}",
                    )

                for ingredient in ingredients:
                    required = ingredient_requirements[ingredient.id]
                    if ingredient.stock_quantity < required:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=(
                                f"Stock insuficiente para ingrediente '{ingredient.name}'. "
                                f"Requerido: {required}, disponible: {ingredient.stock_quantity}"
                            ),
                        )

                for ingredient in ingredients:
                    ingredient.stock_quantity -= ingredient_requirements[ingredient.id]
                    ingredient_repo.update(ingredient.id, ingredient)

            for producto, cantidad in standalone_products:
                producto.stock_quantity -= cantidad
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

            notifs = self._build_notificaciones(
                pedido,
                estado_nuevo_codigo=EstadoPedidoEnum.PENDIENTE,
            )

        # Fuera del with → la transacción ya commiteó (si falló, no llegamos acá)
        self._emit_notificaciones(notifs)
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

    def get_cola_staff(
        self,
        roles: List[str],
        offset: int = 0,
        limit: int = 50,
    ) -> PedidoList:
        """Tablero inicial del staff: pedidos en los estados que VE su rol.

        Usa `ROLE_VISIBILITY` (la misma fuente de verdad que rutea el WS), de
        modo que la lista inicial sea consistente con los eventos `UPSERT`/
        `REMOVE` posteriores. Los estados terminales (`CANCELADO`/`ENTREGADO`)
        se acotan a las últimas 24h; el resto se trae sin bound temporal. El
        front separa el resultado por `estado_codigo` en secciones.
        """
        codigos = estados_visibles(roles)
        with OrderUnitOfWork(self._session) as uow:
            # Mapear código → id de estado
            codigo_a_id = {e.codigo: e.id for e in uow.estados.get_all_ordered()}
            activos_ids = [
                codigo_a_id[c]
                for c in codigos - ESTADOS_TERMINALES
                if c in codigo_a_id
            ]
            terminales_ids = [
                codigo_a_id[c]
                for c in codigos & ESTADOS_TERMINALES
                if c in codigo_a_id
            ]
            recientes_desde = (
                datetime.now(timezone.utc) - timedelta(hours=24)
                if terminales_ids
                else None
            )

            pedidos = uow.pedidos.get_cola(
                activos_ids, terminales_ids, recientes_desde, offset, limit
            )
            total = uow.pedidos.count_cola(
                activos_ids, terminales_ids, recientes_desde
            )
            data = [PedidoPublic.model_validate(p) for p in pedidos]
            return PedidoList(data=data, total=total)

    def get_all_pedidos_admin(
        self,
        estado_id: Optional[int] = None,
        usuario_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 20,
    ) -> List[Pedido]:
        with OrderUnitOfWork(self._session) as uow:
            return uow.pedidos.get_all_admin(estado_id, usuario_id, offset, limit)

    def cambiar_estado_pedido(
        self,
        pedido_id: int,
        cambio: CambioEstadoRequest,
        usuario_cambio_id: Optional[int] = None,
        roles: Optional[List[str]] = None,
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

            if estado_actual == nuevo_estado:
                return pedido

            roles = roles or []
            permitidos = uow.transiciones.roles_permitidos(
                estado_actual.id, nuevo_estado.id
            )

            # La transición no existe para ningún rol → no es parte de la máquina de estados
            if not permitidos:
                destinos = [
                    e.codigo.value
                    for e in uow.transiciones.destinos_validos(
                        estado_actual.id, roles
                    )
                ]
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=(
                        f"Transición inválida: de '{estado_actual.codigo.value}' "
                        f"no se puede ir a '{nuevo_estado.codigo.value}'. "
                        f"Estados permitidos para tu rol: {destinos}"
                    ),
                )

            # La transición existe pero ninguno de los roles del usuario la permite
            if not any(r in permitidos for r in roles):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=(
                        f"Transición no permitida para tu rol: "
                        f"'{estado_actual.codigo.value}' → '{nuevo_estado.codigo.value}'"
                    ),
                )

            pedido.estado_id = nuevo_estado.id
            pedido.updated_at = datetime.now(timezone.utc)

            if nuevo_estado.codigo == EstadoPedidoEnum.CANCELADO:
                # Si se cancela desde admin o desde cambio de estado, devolvemos stock
                self._restore_stock_for_pedido(pedido)

            uow.pedidos.update(pedido.id, pedido)

            self._registrar_cambio_estado(
                uow,
                pedido_id=pedido.id,
                nuevo_estado=cambio.nuevo_estado,
                usuario_cambio_id=usuario_cambio_id,
                observaciones=cambio.observaciones,
            )

            notifs = self._build_notificaciones(
                pedido,
                estado_nuevo_codigo=nuevo_estado.codigo,
                estado_anterior_codigo=estado_actual.codigo,
            )

        self._emit_notificaciones(notifs)
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

            self._restore_stock_for_pedido(pedido)

            self._registrar_cambio_estado(
                uow,
                pedido_id=pedido.id,
                nuevo_estado=EstadoPedidoEnum.CANCELADO,
                usuario_cambio_id=usuario_id,
                observaciones="Cancelado por el cliente",
            )

            notifs = self._build_notificaciones(
                pedido,
                estado_nuevo_codigo=nuevo_estado.codigo,
                estado_anterior_codigo=estado_actual.codigo,
            )

        self._emit_notificaciones(notifs)
        return pedido

    def update_pedido(
        self, pedido_id: int, pedido_in: PedidoUpdate, usuario_id: int
    ) -> Pedido:
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

    def _restore_stock_for_pedido(self, pedido: Pedido) -> None:
        # Recupera stock cuando un pedido se cancela.
        product_repo = ProductRepository(self._session)
        ingredient_repo = IngredientRepository(self._session)
        ingredient_cache: dict[int, object] = {}

        for detalle in pedido.detalles:
            producto = product_repo.get_by_id(detalle.producto_id)
            if not producto:
                continue

            ingredient_links = product_repo.get_ingredient_links(producto.id)
            if ingredient_links:
                # Producto compuesto: devolver ingredientes usados en el pedido
                for link in ingredient_links:
                    ingredient = ingredient_cache.get(link.ingredient_id)
                    if ingredient is None:
                        ingredient = ingredient_repo.get_by_id(link.ingredient_id)
                        if ingredient is None:
                            continue
                        ingredient_cache[link.ingredient_id] = ingredient

                    ingredient.stock_quantity += link.quantity * detalle.cantidad
                    ingredient_repo.update(ingredient.id, ingredient)
            else:
                producto.stock_quantity += detalle.cantidad
                if not producto.available and producto.stock_quantity > 0:
                    producto.available = True
                product_repo.update(producto.id, producto)

    def count_pedidos_by_usuario(self, usuario_id: int) -> int:
        with OrderUnitOfWork(self._session) as uow:
            return uow.pedidos.count_by_usuario(usuario_id)

    def count_pedidos_admin(
        self,
        estado_id: Optional[int] = None,
        usuario_id: Optional[int] = None,
    ) -> int:
        with OrderUnitOfWork(self._session) as uow:
            return uow.pedidos.count_admin(estado_id, usuario_id)

    def get_estados_pedido_ordered(self):
        with OrderUnitOfWork(self._session) as uow:
            return uow.estados.get_all_ordered()

    def get_historial_estados(self, pedido_id: int) -> List[HistorialEstadoPedido]:
        with OrderUnitOfWork(self._session) as uow:
            return uow.historial.get_by_pedido_id(pedido_id)
