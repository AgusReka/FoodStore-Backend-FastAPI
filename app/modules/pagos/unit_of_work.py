from sqlmodel import Session
from app.core.unit_of_work import UnitOfWork
from app.modules.pagos.repository import FormaPagoRepository


class PaymentUnitOfWork(UnitOfWork):
    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self.formas_pago = FormaPagoRepository(session)

    def refresh(self, entity) -> None:
        self._session.refresh(entity)
