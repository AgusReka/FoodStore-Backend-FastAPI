from sqlmodel import Session
from typing import List, Optional
from fastapi import HTTPException, status
from app.modules.pagos.models import FormaPago
from app.modules.pagos.repository import FormaPagoRepository
from app.modules.pagos.unit_of_work import PaymentUnitOfWork
from app.modules.pagos.schemas import FormaPagoCreate, FormaPagoUpdate

class FormaPagoService:
    """
    Service para gestión de formas de pago.
    Operaciones con validaciones básicas.
    """
    def __init__(self, session: Session) -> None:
        self.session = session
        self.uow = PaymentUnitOfWork(session)
        
    def get_formas_pago(self, forma_pago_in: FormaPagoCreate, es_admin: bool = True) ->FormaPago:
        """
        Crea una nueva forma de pago.
        Solo ADMIN puede ejecutar esta operación.
        """
        if not es_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para crear formas de pago."
            )
        #validar que no exista otra forma con el mismo nombre
        existing = self.uow.forma_pago.get_by_nombre(forma_pago_in.nombre)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Ya existe una forma de pago con el nombre '{forma_pago_in.nombre}'."
            )
        forma_pago = FormaPago(*forma_pago_in.model_dump())
        return self.uow.formas_pago.create(forma_pago)
    
    def update_forma_pago(self, forma_pago_id: int, forma_pago_in: FormaPagoUpdate, es_admin: bool = True) -> FormaPago:
        """Actualiza una forma de pago existente."""
        if not es_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo administradores pueden modificar formas de pago"
            )
        
        forma_pago = self.get_forma_pago_by_id(forma_pago_id)
        
        update_data = forma_pago_in.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            if value is not None:
                setattr(forma_pago, field, value)
        
        return self.uow.formas_pago.update(forma_pago_id, forma_pago)
    
    def delete_forma_pago(self, forma_pago_id: int, es_admin: bool = True) -> bool:
        """
        Soft delete de una forma de pago.
        No se puede eliminar si hay pedidos asociados
        """
        if not es_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo administradores pueden eliminar formas de pago"
            )
        forma_pago = self.get_forma_pago_by_id(forma_pago_id)
        
        """validar que no haya pediddos asociados a esta forma de pago
        """
        if self._hay_pedidos_asociados(forma_pago_id):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="No se puede eliminar esta forma de pago porque hay pedidos asociados."
            )
        return self.uow.formas_pago.delete(forma_pago_id)  