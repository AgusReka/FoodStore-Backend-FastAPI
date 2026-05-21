from sqlmodel import Session
from typing import List, Optional
from fastapi import HTTPException, status
from app.modules.direcciones.models import DireccionEntrega
from app.modules.direcciones.repository import DireccionEntregaRepository
from app.modules.direcciones.unit_of_work import AddressUnitOfWork
from app.modules.direcciones.schemas import DireccionEntregaCreate, DireccionEntregaUpdate

class DireccionesService:
    """
    Service para gestión de direcciones de entrega.
    Incluye lógica para manejar la dirección principal por usuario.
    """
    def __init__(self, session: Session) -> None:
        self.session = session
        self.uow = AddressUnitOfWork(session)
        
    def get_direcciones_by_usuario(self, usuario_id: int, offset: int = 0, limit: int = 20) -> List[DireccionEntrega]:
        return self.uow.direcciones.get_by_usuario_id(usuario_id, offset, limit)
    
    def get_direccion_by_id(self, direccion_id: int, usuario_id: int) -> DireccionEntrega:
        direccion = self.uow.direcciones.get_by_id(direccion_id)
        if not direccion or direccion.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Dirección no encontrada."
            )
        if direccion.usuario_id != usuario_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="No tienes permisos para acceder a esta dirección."
            )
        return direccion
    
    def get_direccion_principal(self, usuario_id: int) -> Optional[DireccionEntrega]:
        """Obtiene la dirección principal de un usuario"""
        return self.uow.direcciones.get_principal(usuario_id)
    
    def create_direccion(self, usuario_id: int, direccion_in: DireccionEntregaCreate) -> DireccionEntrega:
        """Crea una nueva dirección. Si se marca como la primera automaticamente desmarca las anteriores"""
        try:
            with self.uow:
                # Si es principal, desmarcar las demás direcciones del usuario
                if direccion_in.es_principal:
                    self.uow.direcciones.marcar_no_principal(usuario_id)
                
                direccion = DireccionEntrega(
                    **direccion_in.model_dump(),
                    usuario_id=usuario_id
                )
                return self.uow.direcciones.create(direccion)
                
        except Exception as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al crear dirección: {str(e)}"
            )
            
    def update_direccion(self, direccion_id: int, usuario_id: int, direccion_in: DireccionEntregaUpdate) -> DireccionEntrega:
        """Actualiza una dirección existente."""
        try:
            with self.uow:
                direccion = self.get_direccion_by_id(direccion_id, usuario_id)
                
                # Si se marca como principal, desmarcar las demás
                if direccion_in.es_principal is True:
                    self.uow.direcciones.marcar_no_principal(usuario_id)
                
                update_data = direccion_in.model_dump(exclude_unset=True)
                for field, value in update_data.items():
                    if value is not None:
                        setattr(direccion, field, value)
                
                return self.uow.direcciones.update(direccion_id, direccion)
                
        except HTTPException:
            self.session.rollback()
            raise
        except Exception as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al actualizar dirección: {str(e)}"
            )
    
    def marcar_como_principal(self, direccion_id: int, usuario_id: int) -> DireccionEntrega:
        """
        Marca una dirección específica como principal para el usuario.
        Automáticamente desmarca cualquier otra dirección principal existent
        """
        try: 
            with self.uow:
                direccion = self.get_direccion_by_id(direccion_id, usuario_id)
                # Desmarcar todas las direcciones principales del usuario
                self.uow.direcciones.marcar_no_principal(usuario_id)
                # Marcar esta como principal
                direccion.es_principal = True
                return self.uow.direcciones.update(direccion_id, direccion)
        except HTTPException:
            self.session.rollback()
            raise
        except Exception as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al marcar dirección principal: {str(e)}"
            )
            
    def delete_direccion(self, direccion_id: int, usuario_id: int) -> bool:
        """Soft delete de una dirección."""
        direccion = self.get_direccion_by_id(direccion_id, usuario_id)        
        return self.uow.direcciones.delete(direccion_id)
        