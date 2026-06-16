from sqlmodel import Session, select
from typing import List, Optional
from app.core.repository import BaseRepository
from app.modules.pagos.models import FormaPago, PagoMP

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
    
    def get_all(self, offset: int = 0, limit: int = 20, include_deleted: bool = False) -> List[FormaPago]:
        """Lista formas de pago, excluyendo soft-deleted por defecto."""
        query = select(FormaPago)
        if not include_deleted:
            query = query.where(FormaPago.deleted_at.is_(None))
        return list(self.session.exec(query.offset(offset).limit(limit)).all())

    def count(self, include_deleted: bool = False) -> int:
        """Cuenta formas de pago respetando el filtro de soft delete."""
        query = select(FormaPago)
        if not include_deleted:
            query = query.where(FormaPago.deleted_at.is_(None))
        return len(self.session.exec(query).all())


class PagoMPRepository(BaseRepository[PagoMP]):
    def __init__(self, session: Session) -> None:
        super().__init__(session, PagoMP)

    def get_by_pedido(self, pedido_id: int) -> Optional[PagoMP]:
        return self.session.exec(
            select(PagoMP).where(PagoMP.pedido_id == pedido_id)
        ).first()

    def get_by_mp_payment_id(self, mp_payment_id: int) -> Optional[PagoMP]:
        return self.session.exec(
            select(PagoMP).where(PagoMP.mp_payment_id == mp_payment_id)
        ).first()

    def get_by_idempotency_key(self, key: str) -> Optional[PagoMP]:
        return self.session.exec(
            select(PagoMP).where(PagoMP.idempotency_key == key)
        ).first()

    def get_latest_by_pedido(self, pedido_id: int) -> Optional[PagoMP]:
        return self.session.exec(
            select(PagoMP)
            .where(PagoMP.pedido_id == pedido_id)
            .order_by(PagoMP.created_at.desc())
        ).first()