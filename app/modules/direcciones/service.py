from sqlmodel import Session
from typing import List, Optional
from fastapi import HTTPException, status
from app.modules.direcciones.models import DireccionEntrega
from app.modules.direcciones.unit_of_work import AddressUnitOfWork
from app.modules.direcciones.schemas import DireccionEntregaCreate, DireccionEntregaUpdate


class DireccionesService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_direcciones_by_usuario(self, usuario_id: int, offset: int = 0, limit: int = 20) -> List[DireccionEntrega]:
        with AddressUnitOfWork(self._session) as uow:
            return uow.direcciones.get_by_usuario_id(usuario_id, offset, limit)

    def get_direccion_by_id(self, direccion_id: int, usuario_id: int) -> DireccionEntrega:
        with AddressUnitOfWork(self._session) as uow:
            direccion = uow.direcciones.get(direccion_id)
            if not direccion or direccion.deleted_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Dirección no encontrada.",
                )
            if direccion.usuario_id != usuario_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permisos para acceder a esta dirección.",
                )
            return direccion

    def get_direccion_principal(self, usuario_id: int) -> Optional[DireccionEntrega]:
        with AddressUnitOfWork(self._session) as uow:
            return uow.direcciones.get_principal(usuario_id)

    def create_direccion(self, usuario_id: int, direccion_in: DireccionEntregaCreate) -> DireccionEntrega:
        with AddressUnitOfWork(self._session) as uow:
            if direccion_in.es_principal:
                uow.direcciones.marcar_no_principal(usuario_id)
            direccion = DireccionEntrega(
                **direccion_in.model_dump(),
                usuario_id=usuario_id,
            )
            return uow.direcciones.create(direccion)

    def update_direccion(self, direccion_id: int, usuario_id: int, direccion_in: DireccionEntregaUpdate) -> DireccionEntrega:
        with AddressUnitOfWork(self._session) as uow:
            direccion = uow.direcciones.get(direccion_id)
            if not direccion or direccion.deleted_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Dirección no encontrada.",
                )
            if direccion.usuario_id != usuario_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permisos para modificar esta dirección.",
                )
            if direccion_in.es_principal is True:
                uow.direcciones.marcar_no_principal(usuario_id)
            update_data = direccion_in.model_dump(exclude_unset=True)
            for field, value in update_data.items():
                if value is not None:
                    setattr(direccion, field, value)
            return uow.direcciones.update(direccion_id, direccion)

    def marcar_como_principal(self, direccion_id: int, usuario_id: int) -> DireccionEntrega:
        with AddressUnitOfWork(self._session) as uow:
            direccion = uow.direcciones.get(direccion_id)
            if not direccion or direccion.deleted_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Dirección no encontrada.",
                )
            if direccion.usuario_id != usuario_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permisos para modificar esta dirección.",
                )
            uow.direcciones.marcar_no_principal(usuario_id)
            direccion.es_principal = True
            return uow.direcciones.update(direccion_id, direccion)

    def delete_direccion(self, direccion_id: int, usuario_id: int) -> None:
        with AddressUnitOfWork(self._session) as uow:
            direccion = uow.direcciones.get(direccion_id)
            if not direccion or direccion.deleted_at is not None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Dirección no encontrada.",
                )
            if direccion.usuario_id != usuario_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permisos para eliminar esta dirección.",
                )
            uow.direcciones.delete(direccion_id)
