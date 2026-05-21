from sqlmodel import Session, select
from typing import List, Optional
from app.core.repository import BaseRepository
from app.modules.pagos.models import FormaPago

class FormaPagoRepository(BaseRepository[FormaPago]):
    """Repository para formas de pago."""
    
    def __init__(self, session: Session) -> None:
        super().__init__(session, FormaPago)
    
    def get_activas(self) -> List[FormaPago]:
        """Obtiene solo las formas de pago activas."""
        return list(
            self.session.exec(
                select(FormaPago)
                .where(FormaPago.is_active == True)
                .where(FormaPago.deleted_at.is_(None))
                .order_by(FormaPago.nombre)
            ).all()
        )
    
    def get_by_nombre(self, nombre: str) -> Optional[FormaPago]:
        """Obtiene una forma de pago por nombre."""
        return self.session.exec(
            select(FormaPago).where(FormaPago.nombre == nombre)
        ).first()
    
    def count(self) -> int:
        """Cuenta todas las formas de pago."""
        return len(self.session.exec(select(FormaPago)).all())