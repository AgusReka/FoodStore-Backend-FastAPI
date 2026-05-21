from sqlmodel import Session
from app.core.unit_of_work import UnitOfWork
from app.modules.pedidos.repository import (
    PedidoRepository,
    DetallePedidoRepository,
    EstadoPedidoRepository,
    HistorialEstadoPedidoRepository,
)


class OrderUnitOfWork(UnitOfWork):
    def __init__(self, session: Session) -> None:
        super().__init__(session)
        self.pedidos = PedidoRepository(session)
        self.detalles = DetallePedidoRepository(session)
        self.estados = EstadoPedidoRepository(session)
        self.historial = HistorialEstadoPedidoRepository(session)

    def refresh(self, entity) -> None:
        self._session.refresh(entity)
