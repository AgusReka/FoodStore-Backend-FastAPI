from typing import Annotated
from fastapi import APIRouter, Depends, Query
from sqlmodel import Session

from app.core.database import get_session
from app.core.deps import require_admin
from app.modules.user.models import User
from app.modules.stats.schemas import (
    DashboardStats,
    TicketEvolutionItem,
    OrdersByStatus,
    OrdersByDayItem,
)
from app.modules.stats.service import StatsService

router = APIRouter()


def get_stats_service(session: Session = Depends(get_session)) -> StatsService:
    return StatsService(session)


@router.get(
    "/dashboard",
    response_model=DashboardStats,
    summary="KPIs agregados para el dashboard del admin",
)
def dashboard_stats(
    _: Annotated[User, Depends(require_admin)],
    svc: StatsService = Depends(get_stats_service),
) -> DashboardStats:
    return svc.get_dashboard()


@router.get(
    "/ticket-evolution",
    response_model=list[TicketEvolutionItem],
    summary="Evolución del ticket promedio por día (gráfico de línea)",
)
def ticket_evolution(
    _: Annotated[User, Depends(require_admin)],
    svc: StatsService = Depends(get_stats_service),
    days: int = Query(30, ge=7, le=90, description="Cantidad de días hacia atrás"),
) -> list[TicketEvolutionItem]:
    return svc.get_ticket_evolution(days)


@router.get(
    "/orders-by-status",
    response_model=OrdersByStatus,
    summary="Pedidos agrupados por estado actual (gráfico de torta)",
)
def orders_by_status(
    _: Annotated[User, Depends(require_admin)],
    svc: StatsService = Depends(get_stats_service),
) -> OrdersByStatus:
    return svc.get_orders_by_status()


@router.get(
    "/orders-by-day",
    response_model=list[OrdersByDayItem],
    summary="Pedidos por día (gráfico de barras semanal)",
)
def orders_by_day(
    _: Annotated[User, Depends(require_admin)],
    svc: StatsService = Depends(get_stats_service),
    days: int = Query(7, ge=1, le=90, description="Cantidad de días hacia atrás"),
) -> list[OrdersByDayItem]:
    return svc.get_orders_by_day(days)
