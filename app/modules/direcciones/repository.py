from sqlmodel import Session, select
from typing import List, Optional
from app.core.repository import BaseRepository
from app.modules.direcciones.models import DireccionEntrega

class DireccionEntregaRepository(BaseRepository[DireccionEntrega]):
    """Repository para direcciones de entrega."""
    
    def __init__(self, session: Session) -> None:
        super().__init__(session, DireccionEntrega)
    
    def get_by_usuario_id(
        self, 
        usuario_id: int,
        offset: int = 0,
        limit: int = 20
    ) -> List[DireccionEntrega]:
        """Obtiene las direcciones de un usuario."""
        return list(
            self.session.exec(
                select(DireccionEntrega)
                .where(DireccionEntrega.usuario_id == usuario_id)
                .where(DireccionEntrega.deleted_at.is_(None))
                .order_by(DireccionEntrega.es_principal.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )
    def get_principal(self, usuario_id: int) -> Optional[DireccionEntrega]:
        """Obtiene la dirección principal de un usuario."""
        return self.session.exec(
            select(DireccionEntrega)
            .where(DireccionEntrega.usuario_id == usuario_id)
            .where(DireccionEntrega.es_principal == True)
            .where(DireccionEntrega.deleted_at.is_(None))
        ).first()
    
    def marcar_no_principal(self, usuario_id: int) -> None:
        """Marca todas las direcciones de un usuario como no principales."""
        direcciones = self.session.exec(
            select(DireccionEntrega)
            .where(DireccionEntrega.usuario_id == usuario_id)
            .where(DireccionEntrega.es_principal == True)
            .where(DireccionEntrega.deleted_at.is_(None))
        ).all()
        
        for direccion in direcciones:
            direccion.es_principal = False
            
    def count_by_usuario(self, usuario_id: int) -> int:
        """Cuenta las direcciones de un usuario."""
        return len(
            self.session.exec(
                select(DireccionEntrega)
                .where(DireccionEntrega.usuario_id == usuario_id)
                .where(DireccionEntrega.deleted_at.is_(None))
            ).all()
        )