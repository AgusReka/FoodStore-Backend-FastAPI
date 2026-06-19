from datetime import datetime, timedelta, timezone, date
from decimal import Decimal
from sqlmodel import Session

from app.modules.stats.repository import StatsRepository
from app.modules.stats.schemas import (
    DashboardStats,
    TicketEvolutionItem,
    OrdersByStatus,
    OrdersByDayItem,
)
from app.modules.pedidos.schemas import EstadoPedidoEnum


class StatsService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = StatsRepository(session)

    def get_dashboard(self) -> DashboardStats:
        now = datetime.now(timezone.utc)
        start_of_day = now.replace(hour=0, minute=0, second=0, microsecond=0)
        start_of_week = start_of_day - timedelta(days=7)

        pedidos_hoy = self._repo.count_pedidos_hoy(start_of_day)
        ganancia_hoy = self._repo.sum_ganancia_hoy(start_of_day)
        pedidos_pendientes = self._repo.count_pedidos_pendientes()
        pedidos_semana = self._repo.count_pedidos_semana(start_of_week)
        productos_activos = self._repo.count_productos_activos()
        productos_bajo_stock = self._repo.count_productos_bajo_stock()
        ingredientes_activos = self._repo.count_ingredientes_activos()
        ingredientes_bajo_stock = self._repo.count_ingredientes_bajo_stock()

        pedidos_hoy_int = int(pedidos_hoy or 0)
        ticket_promedio_hoy = (
            (ganancia_hoy / pedidos_hoy_int) if pedidos_hoy_int > 0 else Decimal(0)
        )
        
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
        
    def get_ticket_evolution(self, days: int = 30) -> list[TicketEvolutionItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = self._repo.get_ticket_evolution(cutoff)
        return [
            TicketEvolutionItem(
                date=row[0],
                avg_ticket=Decimal(str(row[1])).quantize(Decimal("0.01")),
            )
            for row in rows
        ]

    def get_orders_by_status(self) -> OrdersByStatus:
        counts = self._repo.get_orders_by_status()
        return OrdersByStatus(
            pendiente=counts.get(EstadoPedidoEnum.PENDIENTE, 0),
            confirmado=counts.get(EstadoPedidoEnum.CONFIRMADO, 0),
            en_preparacion=counts.get(EstadoPedidoEnum.EN_PREP, 0),
            listo=counts.get(EstadoPedidoEnum.LISTO, 0),
            entregado=counts.get(EstadoPedidoEnum.ENTREGADO, 0),
            cancelado=counts.get(EstadoPedidoEnum.CANCELADO, 0),
        )

    def get_orders_by_day(self, days: int = 7) -> list[OrdersByDayItem]:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        rows = self._repo.get_orders_by_day(cutoff)

        DAY_NAMES = {
            0: "Lunes", 1: "Martes", 2: "Miércoles",
            3: "Jueves", 4: "Viernes", 5: "Sábado", 6: "Domingo",
        }
        counts_by_date: dict[date, int] = {row[0]: int(row[1]) for row in rows}

        today = datetime.now(timezone.utc).date()
        result = []
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
