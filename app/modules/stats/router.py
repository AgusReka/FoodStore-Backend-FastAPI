from typing import Annotated
from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.core.database import get_session
from app.core.deps import require_admin
from app.modules.user.models import User
from app.modules.stats.schemas import DashboardStats
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
