from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from sqlalchemy import func, cast, Date
from sqlmodel import Session, select

from app.modules.pedidos.models import Pedido, EstadoPedido
from app.modules.pedidos.schemas import EstadoPedidoEnum
from app.modules.product.models import Product, ProductIngredientLink
from app.modules.ingredient.models import Ingredient
from app.modules.stats.schemas import OrdersByDayItem, TicketEvolutionItem

LOW_STOCK_THRESHOLD = 10
PENDING_STATES = (
    EstadoPedidoEnum.PENDIENTE,
    EstadoPedidoEnum.CONFIRMADO,
    EstadoPedidoEnum.EN_PREP,
    EstadoPedidoEnum.LISTO,
)

class StatsRepository:
    def __init__(self, session: Session) -> None:
        self.session = session
        
    def count_pedidos_hoy(self, start_of_day: datetime) -> int:
    # ── Pedidos hoy (no eliminados, cualquier estado) ──────────────────
        return self.session.exec(
            select(func.count(Pedido.id)).where(
                Pedido.created_at >= start_of_day,
                Pedido.deleted_at.is_(None),
            )
        ).one()
    
    def sum_ganancia_hoy(self, start_of_day: datetime) -> Decimal:
    # ── Ganancia hoy: suma de `total` de pedidos NO cancelados de hoy ──
        result = self.session.exec(
            select(func.coalesce(func.sum(Pedido.total), 0))
            .join(EstadoPedido, EstadoPedido.id == Pedido.estado_id)
            .where(
                Pedido.created_at >= start_of_day,
                Pedido.deleted_at.is_(None),
                EstadoPedido.codigo != EstadoPedidoEnum.CANCELADO,
            )
        ).one()
        return Decimal(result or 0)
        
        
    def count_pedidos_pendientes(self) -> int:
    # ── Pedidos pendientes (estados en curso) ──────────────────────────
        return self.session.exec(
            select(func.count(Pedido.id))
            .join(EstadoPedido, EstadoPedido.id == Pedido.estado_id)
            .where(
                Pedido.deleted_at.is_(None),
                EstadoPedido.codigo.in_(PENDING_STATES),
            )
        ).one()
        
    def count_pedidos_semana(self, start_of_week: datetime) -> int:
    # ── Pedidos últimos 7 días ─────────────────────────────────────────
        return self.session.exec(
            select(func.count(Pedido.id)).where(
                Pedido.created_at >= start_of_week,
                Pedido.deleted_at.is_(None),
            )
        ).one()
        
    def count_productos_activos(self) -> int:
    # ── Productos activos (no soft-deleted) ────────────────────────────
        return self.session.exec(
            select(func.count(Product.id)).where(Product.deleted_at.is_(None))
        ).one()
        
    def count_productos_bajo_stock(self) -> int:
    # ── Productos con stock bajo (solo standalone, sin receta) ─────────
        # Los productos con ingredientes consumen stock de Ingredient, no del
        # propio Product, así que su stock_quantity no es métrica útil.
        has_recipe = select(ProductIngredientLink.product_id).where(
            ProductIngredientLink.product_id == Product.id
        )
        return self.session.exec(
            select(func.count(Product.id)).where(
                Product.deleted_at.is_(None),
                Product.stock_quantity < LOW_STOCK_THRESHOLD,
                ~has_recipe.exists(),
            )
        ).one()
        
    def count_ingredientes_activos(self) -> int:
    # ── Ingredientes activos ───────────────────────────────────────────
        return self.session.exec(
            select(func.count(Ingredient.id)).where(
                Ingredient.deleted_at.is_(None),
                Ingredient.is_active.is_(True),
            )
        ).one()
        
    def count_ingredientes_bajo_stock(self) -> int:
    # ── Ingredientes con stock bajo ────────────────────────────────────
        return self.session.exec(
            select(func.count(Ingredient.id)).where(
                Ingredient.deleted_at.is_(None),
                Ingredient.is_active.is_(True),
                Ingredient.stock_quantity < LOW_STOCK_THRESHOLD,
            )
        ).one()
        
    # ─────────────────────────────────────────────────────────────────────
    # Ticket promedio por día (línea)
    # ─────────────────────────────────────────────────────────────────────
    def get_ticket_evolution(self, cutoff: datetime):
        rows = self.session.exec(
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
        return rows
        
    def get_orders_by_status(self):
        counts = dict(
            self.session.exec(
                select(EstadoPedido.codigo, func.count(Pedido.id))
                .join(Pedido, Pedido.estado_id == EstadoPedido.id)
                .where(Pedido.deleted_at.is_(None))
                .group_by(EstadoPedido.codigo)
            ).all()
        )
        return counts
    
    def get_orders_by_day(self, cutoff: datetime):
        rows = self.session.exec(
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
        return rows
