from sqlmodel import Session
from typing import Optional
from fastapi import HTTPException, status
from app.modules.pagos.models import FormaPago
from app.modules.pagos.unit_of_work import PaymentUnitOfWork
from app.modules.pagos.schemas import FormaPagoCreate, FormaPagoUpdate, FormaPagoList


class FormaPagoService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_all(self, offset: int = 0, limit: int = 20, include_deleted: bool = False) -> FormaPagoList:
        with PaymentUnitOfWork(self._session) as uow:
            formas_pago = list(uow.formas_pago.get_all(offset=offset, limit=limit, include_deleted=include_deleted))
            total = uow.formas_pago.count(include_deleted=include_deleted)
            return FormaPagoList(data=formas_pago, total=total)

    def get_forma_pago_by_id(self, forma_pago_id: int) -> FormaPago:
        with PaymentUnitOfWork(self._session) as uow:
            forma_pago = uow.formas_pago.get(forma_pago_id)
            if not forma_pago or forma_pago.deleted_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Forma de pago ID {forma_pago_id} no encontrada",
                )
            return forma_pago

    def create_forma_pago(self, forma_pago_in: FormaPagoCreate, es_admin: bool = True) -> FormaPago:
        if not es_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para crear formas de pago.",
            )
        with PaymentUnitOfWork(self._session) as uow:
            existing = uow.formas_pago.get_by_nombre(forma_pago_in.nombre)
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail=f"Ya existe una forma de pago con el nombre '{forma_pago_in.nombre}'.",
                )
            forma_pago = FormaPago(**forma_pago_in.model_dump())
            return uow.formas_pago.create(forma_pago)

    def update_forma_pago(self, forma_pago_id: int, forma_pago_in: FormaPagoUpdate, es_admin: bool = True) -> FormaPago:
        if not es_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo administradores pueden modificar formas de pago",
            )
        with PaymentUnitOfWork(self._session) as uow:
            forma_pago = uow.formas_pago.get(forma_pago_id)
            if not forma_pago or forma_pago.deleted_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Forma de pago ID {forma_pago_id} no encontrada",
                )
            update_data = forma_pago_in.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if value is not None:
                    setattr(forma_pago, field, value)
            return uow.formas_pago.update(forma_pago_id, forma_pago)

    def delete_forma_pago(self, forma_pago_id: int, es_admin: bool = True) -> None:
        if not es_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Solo administradores pueden eliminar formas de pago",
            )
        with PaymentUnitOfWork(self._session) as uow:
            forma_pago = uow.formas_pago.get(forma_pago_id)
            if not forma_pago or forma_pago.deleted_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Forma de pago ID {forma_pago_id} no encontrada",
                )
            uow.formas_pago.delete(forma_pago_id)
