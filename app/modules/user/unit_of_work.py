from sqlmodel import Session
from app.core.unit_of_work import UnitOfWork
from app.modules.user.repository import UserRepository


class UserUnitOfWork(UnitOfWork):
    def __init__(self, session: Session) -> None:

        super().__init__(session)
        self.users = UserRepository(session)

    def refresh(self, entity):
        self._session.refresh(entity)