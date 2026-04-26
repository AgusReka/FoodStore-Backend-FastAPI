from sqlmodel import Session
from app.core.unit_of_work import UnitOfWork
from app.modules.category.repository import CategoryRepository


class CategoryUnitOfWork(UnitOfWork):
    def __init__(self, session: Session) -> None:

        super().__init__(session)
        self.category = CategoryRepository(session)

    def refresh(self, entity):
        self.session.refresh(entity)
