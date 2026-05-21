from sqlmodel import Session, select
from sqlmodel.sql.expression import SelectOfScalar
from typing import List, Optional
from app.core.repository import BaseRepository
from app.modules.pedidos.models import (
    Pedido,
    DetallePedido,
    EstadoPedido,
    HistorialEstadoPedido,
    EstadoPedidoEnum
)

class EstadoPedidoRepository(BaseRepository[EstadoPedido]):
    """Repository para estados de pedido (tabla de referencia)."""
    
    def __init__(self, session: Session) -> None:
        super().__init__(session, EstadoPedido)
    
    def get_by_codigo(self, codigo: EstadoPedidoEnum) -> Optional[EstadoPedido]:
        """Obtiene un estado por su código."""
        return self.session.exec(
            select(EstadoPedido).where(EstadoPedido.codigo == codigo)
        ).first()
    
    def get_all_ordered(self) -> List[EstadoPedido]:
        """Obtiene todos los estados ordenados por progreso."""
        return list(
            self.session.exec(
                select(EstadoPedido).order_by(EstadoPedido.orden)
            ).all()
        )
        
class DetallePedidoRepository(BaseRepository[DetallePedido]):
    """Repository para detalles de pedido."""
    
    def __init__(self, session: Session) -> None:
        super().__init__(session, DetallePedido)
    
    def get_by_pedido_id(self, pedido_id: int) -> List[DetallePedido]:
        """Obtiene todos los detalles de un pedido."""
        return list(
            self.session.exec(
                select(DetallePedido).where(
                    DetallePedido.pedido_id == pedido_id
                )
            ).all()
        )
        
class HistorialEstadoPedidoRepository(BaseRepository[HistorialEstadoPedido]):
    """
    Repository para historial de estados
    Solo permite INSERTs, nunca UPDATE/DELETE
    """
    
    def __init__(self, session: Session) -> None:
        super().__init__(session, HistorialEstadoPedido)
    
    def get_by_pedido_id(self, pedido_id: int) -> List[HistorialEstadoPedido]:
        """Obtiene el historial completo de un pedido ordenado por fecha."""
        return list(
            self.session.exec(
                select(HistorialEstadoPedido)
                .where(HistorialEstadoPedido.pedido_id == pedido_id)
                .order_by(HistorialEstadoPedido.fecha_cambio.desc())
            ).all()
        )
        
class PedidoRepository(BaseRepository[Pedido]):
    """Repository para pedidos con queries específicas."""
    
    def __init__(self, session: Session) -> None:
        super().__init__(session, Pedido)
    
    def get_by_usuario_id(
        self, 
        usuario_id: int, 
        offset: int = 0, 
        limit: int = 20
    ) -> List[Pedido]:
        """Obtiene los pedidos de un usuario específico."""
        return list(
            self.session.exec(
                select(Pedido)
                .where(Pedido.usuario_id == usuario_id)
                .where(Pedido.deleted_at.is_(None))
                .order_by(Pedido.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )
    
    def get_all_admin(
        self,
        estado_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 20
    ) -> List[Pedido]:
        """
        Obtiene todos los pedidos (vista admin).
        Puede filtrar por estado.
        """
        query = select(Pedido).where(Pedido.deleted_at.is_(None))
        
        if estado_id is not None:
            query = query.where(Pedido.estado_id == estado_id)
        
        return list(
            self.session.exec(
                query.order_by(Pedido.created_at.desc()).offset(offset).limit(limit)
            ).all()
        )
    
    def count_by_usuario(self, usuario_id: int) -> int:
        """Cuenta los pedidos de un usuario."""
        return len(
            self.session.exec(
                select(Pedido)
                .where(Pedido.usuario_id == usuario_id)
                .where(Pedido.deleted_at.is_(None))
            ).all()
        )
    
    def count_admin(self, estado_id: Optional[int] = None) -> int:
        """Cuenta todos los pedidos (vista admin)."""
        query = select(Pedido).where(Pedido.deleted_at.is_(None))
        
        if estado_id is not None:
            query = query.where(Pedido.estado_id == estado_id)
        
        return len(self.session.exec(query).all())
        

