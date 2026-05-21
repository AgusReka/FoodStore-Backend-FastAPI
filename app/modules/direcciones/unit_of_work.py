from sqlmodel import Session
from app.modules.direcciones.repository import DireccionEntregaRepository

class AddressUnitOfWork:
    
    def __init__(self, session: Session) -> None:
        self.session = session
        # Inicializar todos los repositorios que participan en la transacción
        self.direcciones = DireccionEntregaRepository(session)

    def refresh(self, entity):
        self.session.refresh(entity)