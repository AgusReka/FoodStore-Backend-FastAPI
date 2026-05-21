from sqlmodel import Session
from app.core.unit_of_work import UnitOfWork
from app.modules.direcciones.repository import DireccionEntregaRepository


class AddressUnitOfWork(UnitOfWork):
    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self.direcciones = DireccionEntregaRepository(session)

    def refresh(self, entity) -> None:
        self._session.refresh(entity)
