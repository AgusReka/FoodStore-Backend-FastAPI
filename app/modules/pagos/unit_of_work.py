from sqlmodel import Session
from app.modules.pagos.repository import FormaPagoRepository

class PaymentUnitOfWork:
    
    def __init__(self, session: Session) -> None:
        self.session = session
        # Inicializar todos los repositorios que participan en la transacción
        self.formas_pago = FormaPagoRepository(session)
    
    def refresh(self, entity):
        self.session.refresh(entity)