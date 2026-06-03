from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, cast, Date
from sqlmodel import Session, select

from app.modules.stats.schemas import (
    DashboardStats,
    TicketEvolutionItem,
    OrdersByStatus,
    OrdersByDayItem,
)
from app.modules.pedidos.models import Pedido, EstadoPedido
from app.modules.pedidos.schemas import EstadoPedidoEnum
from app.modules.product.models import Product, ProductIngredientLink
from app.modules.ingredient.models import Ingredient


# Umbral para "bajo stock" — alineado con el front (LowStockSection).
LOW_STOCK_THRESHOLD = 10

# Estados que se consideran "pendientes" (en curso, no finalizados ni cancelados).
PENDING_STATES = (
    EstadoPedidoEnum.PENDIENTE,
    EstadoPedidoEnum.CONFIRMADO,
    EstadoPedidoEnum.EN_PREP,
    EstadoPedidoEnum.LISTO,
)


class StatsService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_dashboard(self) -> DashboardStats:
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_week = start_of_day - timedelta(days=7)

        # ── Pedidos hoy (no eliminados, cualquier estado) ──────────────────
        pedidos_hoy = self._session.exec(
            select(func.count(Pedido.id)).where(
                Pedido.created_at >= start_of_day,
                Pedido.deleted_at.is_(None),
            )
        ).one()

        # ── Ganancia hoy: suma de `total` de pedidos NO cancelados de hoy ──
        ganancia_hoy_raw = self._session.exec(
            select(func.coalesce(func.sum(Pedido.total), 0))
            .join(EstadoPedido, EstadoPedido.id == Pedido.estado_id)
            .where(
                Pedido.created_at >= start_of_day,
                Pedido.deleted_at.is_(None),
                EstadoPedido.codigo != EstadoPedidoEnum.CANCELADO,
            )
        ).one()
        ganancia_hoy = Decimal(ganancia_hoy_raw or 0)

        pedidos_hoy_int = int(pedidos_hoy or 0)
        ticket_promedio_hoy = (
            (ganancia_hoy / pedidos_hoy_int) if pedidos_hoy_int > 0 else Decimal(0)
        )

        # ── Pedidos pendientes (estados en curso) ──────────────────────────
        pedidos_pendientes = self._session.exec(
            select(func.count(Pedido.id))
            .join(EstadoPedido, EstadoPedido.id == Pedido.estado_id)
            .where(
                Pedido.deleted_at.is_(None),
                EstadoPedido.codigo.in_(PENDING_STATES),
            )
        ).one()

        # ── Pedidos últimos 7 días ─────────────────────────────────────────
        pedidos_semana = self._session.exec(
            select(func.count(Pedido.id)).where(
                Pedido.created_at >= start_of_week,
                Pedido.deleted_at.is_(None),
            )
        ).one()

        # ── Productos activos (no soft-deleted) ────────────────────────────
        productos_activos = self._session.exec(
            select(func.count(Product.id)).where(Product.deleted_at.is_(None))
        ).one()

        # ── Productos con stock bajo (solo standalone, sin receta) ─────────
        # Los productos con ingredientes consumen stock de Ingredient, no del
        # propio Product, así que su stock_quantity no es métrica útil.
        has_recipe = select(ProductIngredientLink.product_id).where(
            ProductIngredientLink.product_id == Product.id
        )
        productos_bajo_stock = self._session.exec(
            select(func.count(Product.id)).where(
                Product.deleted_at.is_(None),
                Product.stock_quantity < LOW_STOCK_THRESHOLD,
                ~has_recipe.exists(),
            )
        ).one()

        # ── Ingredientes activos ───────────────────────────────────────────
        ingredientes_activos = self._session.exec(
            select(func.count(Ingredient.id)).where(
                Ingredient.deleted_at.is_(None),
                Ingredient.is_active.is_(True),
            )
        ).one()

        # ── Ingredientes con stock bajo ────────────────────────────────────
        ingredientes_bajo_stock = self._session.exec(
            select(func.count(Ingredient.id)).where(
                Ingredient.deleted_at.is_(None),
                Ingredient.is_active.is_(True),
                Ingredient.stock_quantity < LOW_STOCK_THRESHOLD,
            )
        ).one()

        return DashboardStats(
            pedidos_hoy=pedidos_hoy_int,
            ganancia_hoy=ganancia_hoy.quantize(Decimal("0.01")),
            ticket_promedio_hoy=ticket_promedio_hoy.quantize(Decimal("0.01")),
            pedidos_pendientes=int(pedidos_pendientes or 0),
            pedidos_semana=int(pedidos_semana or 0),
            productos_activos=int(productos_activos or 0),
            productos_bajo_stock=int(productos_bajo_stock or 0),
            ingredientes_activos=int(ingredientes_activos or 0),
            ingredientes_bajo_stock=int(ingredientes_bajo_stock or 0),
        )

    # ─────────────────────────────────────────────────────────────────────
    # Ticket promedio por día (línea)
    # ─────────────────────────────────────────────────────────────────────
    def get_ticket_evolution(self, days: int = 30) -> list[TicketEvolutionItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = self._session.exec(
            select(
                cast(Pedido.created_at, Date).label("date"),
                func.avg(Pedido.total).label("avg_ticket"),
            )
            .join(EstadoPedido, EstadoPedido.id == Pedido.estado_id)
            .where(
                Pedido.created_at >= cutoff,
                Pedido.deleted_at.is_(None),
                EstadoPedido.codigo != EstadoPedidoEnum.CANCELADO,
            )
            .group_by(cast(Pedido.created_at, Date))
            .order_by(cast(Pedido.created_at, Date))
        ).all()

        return [
            TicketEvolutionItem(
                date=row[0],
                avg_ticket=Decimal(str(row[1])).quantize(Decimal("0.01")),
            )
            for row in rows
        ]

    # ─────────────────────────────────────────────────────────────────────
    # Pedidos agrupados por estado actual (torta)
    # ─────────────────────────────────────────────────────────────────────
    def get_orders_by_status(self) -> OrdersByStatus:
        counts: dict[str, int] = dict(
            self._session.exec(
                select(EstadoPedido.codigo, func.count(Pedido.id))
                .join(Pedido, Pedido.estado_id == EstadoPedido.id)
                .where(Pedido.deleted_at.is_(None))
                .group_by(EstadoPedido.codigo)
            ).all()
        )

        return OrdersByStatus(
            pendiente=counts.get(EstadoPedidoEnum.PENDIENTE, 0),
            confirmado=counts.get(EstadoPedidoEnum.CONFIRMADO, 0),
            en_preparacion=counts.get(EstadoPedidoEnum.EN_PREP, 0),
            listo=counts.get(EstadoPedidoEnum.LISTO, 0),
            entregado=counts.get(EstadoPedidoEnum.ENTREGADO, 0),
            cancelado=counts.get(EstadoPedidoEnum.CANCELADO, 0),
        )

    # ─────────────────────────────────────────────────────────────────────
    # Pedidos por día (barras semanal)
    # ─────────────────────────────────────────────────────────────────────
    def get_orders_by_day(self, days: int = 7) -> list[OrdersByDayItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = self._session.exec(
            select(
                cast(Pedido.created_at, Date).label("date"),
                func.count(Pedido.id).label("count"),
            )
            .where(
                Pedido.created_at >= cutoff,
                Pedido.deleted_at.is_(None),
            )
            .group_by(cast(Pedido.created_at, Date))
            .order_by(cast(Pedido.created_at, Date))
        ).all()

        DAY_NAMES = {
            0: "Lunes", 1: "Martes", 2: "Miércoles",
            3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo",
        }

        # Indexar resultados por fecha
        counts_by_date: dict[date, int] = {}
        for row in rows:
            counts_by_date[row[0]] = int(row[1])

        # Rellenar todos los días del rango, incluso sin pedidos
        today = datetime.now(timezone.utc).date()
        result: list[OrdersByDayItem] = []
        for i in range(days):
            d = today - timedelta(days=days - 1 - i)
            result.append(
                OrdersByDayItem(
                    date=d,
                    day_name=DAY_NAMES[d.weekday()],
                    count=counts_by_date.get(d, 0),
                )
            )

        return result
