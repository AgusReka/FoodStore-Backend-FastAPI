from sqlmodel import Session
from app.modules.stats.repository import StatsRepository
from app.modules.stats.service import StatsService

class StatsUnitOfWork:
    def __init__(self, session: Session):
        self.repository = StatsRepository(session)
        self.service = StatsService(session)