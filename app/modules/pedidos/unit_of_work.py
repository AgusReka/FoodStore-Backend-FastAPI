from sqlmodel import Session
from app.modules.pedidos.repository import (
    PedidoRepository,
    DetallePedidoRepository,
    EstadoPedidoRepository,
    HistorialEstadoPedidoRepository
)

class OrderUnitOfWork:
    """
    Agrupar múltiples operaciones de repositorio en una transacción atómica
    Garantizar que todas las operaciones se completen (commit) o ninguna (rollback)
    El Service NUNCA llama a session.commit() directamente
    """
    
    def __init__(self, session: Session) -> None:
        self.session = session
        # Inicializar todos los repositorios que participan en la transacción
        self.pedidos = PedidoRepository(session)
        self.detalles = DetallePedidoRepository(session)
        self.estados = EstadoPedidoRepository(session)
        self.historial = HistorialEstadoPedidoRepository(session)
    
    def refresh(self, entity):
        self.session.refresh(entity)