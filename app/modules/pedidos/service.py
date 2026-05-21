from sqlmodel import Session
from typing import List, Optional
from datetime import datetime, timezone
from decimal import Decimal
from fastapi import HTTPException, status
from app.modules.pedidos.unit_of_work import OrderUnitOfWork
from app.modules.pedidos.models import (
    Pedido,
    DetallePedido,
    EstadoPedido,
    HistorialEstadoPedido,
    EstadoPedidoEnum
)
from app.modules.pedidos.repository import (
    PedidoRepository,
    DetallePedidoRepository,
    EstadoPedidoRepository,
    HistorialEstadoPedidoRepository
)
from app.modules.pedidos.schemas import (
    PedidoCreate,
    PedidoUpdate,
    CambioEstadoRequest,
    DetallePedidoCreate
)
from app.modules.product.repository import ProductRepository

class PedidoService:
    """
    Service para gestión de pedidos.
    Contiene toda la lógica de negocio relacionada con pedidos.
    """
    def __init__(self, session: Session) -> None:
        self.session = session
        self.uow = OrderUnitOfWork(session)
        self.product_repo = ProductRepository(session)
        
    # CREACIÓN DE PEDIDO - Transacción Atómica
    def crear_pedido(self, usuario_id: int, pedido_in: PedidoCreate) -> Pedido:
        """
        Crea un nuevo pedido con todos sus detalles en una transacción atómica.
        PATRONES APLICADOS:
        - Guarda precio y nombre inmutables del producto
        - Validación de stock: Verifica disponibilidad antes de crear
        """
        try:
            with self.uow:
                # 1. Validar que el usuario tenga al menos un detalle
                if not pedido_in.detalles:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="El pedido debe contener al menos un producto"
                    )
                    
                # 2. Calcular totales y validar stock de cada producto
                subtotal = Decimal("0.00")
                detalles_a_crear = []
                
                for detalle_in in pedido_in.detalles:
                    # Obtener producto desde DB
                    producto = self.product_repo.get(detalle_in.producto_id)
                    
                    if not producto:
                        raise HTTPException(
                            status_code=status.HTTP_404_NOT_FOUND,
                            detail=f"Producto ID {detalle_in.producto_id} no encontrado"
                        )
                    
                    if not producto.disponible:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"Producto '{producto.nombre}' no está disponible"
                        )
                    
                    if producto.stock_cantidad < detalle_in.cantidad:
                        raise HTTPException(
                            status_code=status.HTTP_409_CONFLICT,
                            detail=f"Stock insuficiente para '{producto.nombre}'. Disponible: {producto.stock_cantidad}"
                        )
                    
                    precio_unitario = producto.precio
                    nombre_producto = producto.nombre
                    
                    # Calcular subtotal del detalle
                    subtotal_detalle = precio_unitario * detalle_in.cantidad
                    subtotal += subtotal_detalle
                    
                    # Preparar detalle para creación
                    detalles_a_crear.append({
                        "producto_id": detalle_in.producto_id,
                        "producto_nombre": nombre_producto,
                        "producto_precio_unitario": precio_unitario,
                        "cantidad": detalle_in.cantidad,
                        "subtotal": subtotal_detalle
                    })
                    
                    # DESCONTAR STOCK inmediatamente (dentro de la transacción)
                    producto.stock_cantidad -= detalle_in.cantidad
                    if producto.stock_cantidad == 0:
                        producto.disponible = False
                    self.product_repo.update(producto.id, producto)
                    
                # 3. Calcular total (subtotal + envío - por ahora envío = 0)
                costo_envio = Decimal("0.00")  # Implementar lógica de envío
                total = subtotal + costo_envio 
                
                # 4. Crear el pedido principal
                pedido_data = pedido_in.model_dump(exclude={"detalles"})
                pedido = Pedido(
                    **pedido_data,
                    usuario_id=usuario_id,
                    estado_id=1,  # PENDIENTE por defecto
                    subtotal=subtotal,
                    costo_envio=costo_envio,
                    total=total
                )
                self.uow.pedidos.create(pedido)
                self.session.flush()  # Obtener ID generado
                # 5. Crear todos los detalles del pedido
                for detalle_data in detalles_a_crear:
                    detalle = DetallePedido(
                        pedido_id=pedido.id,
                        **detalle_data
                    )
                    self.uow.detalles.create(detalle)
                
                # 6. Registrar primer estado en el historial (AUDIT TRAIL)
                self._registrar_cambio_estado(
                    pedido_id=pedido.id,
                    nuevo_estado=EstadoPedidoEnum.PENDIENTE,
                    observaciones="Pedido creado exitosamente"
                )
                
                # 7. COMMIT automático al salir del contexto 'with'
                return pedido
        except HTTPException:
            # ROLLBACK automático si hay error de negocio
            self.session.rollback()
            raise
        except Exception as e:
            # ROLLBACK para cualquier error inesperado
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al crear el pedido: {str(e)}"
            )
            
    def get_pedido_by_id(self, pedido_id: int, usuario_id: Optional[int] = None, es_admin: bool = False) -> Pedido:
        """
        Obtiene un pedido por ID con validación de permisos.
        
        - cliente: Solo puede ver sus propios pedidos
        - admin: Pueden ver cualquier pedido
        """
        pedido = self.uow.pedidos.get(pedido_id)
        
        if not pedido or pedido.deleted_at is not None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Pedido no encontrado"
            )
        # Validar permisos si se proporciona usuario_id
        if usuario_id is not None and not es_admin:
            if pedido.usuario_id != usuario_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="No tienes permiso para ver este pedido"
                )
        
        return pedido
    
    def get_pedidos_by_usuario(
        self, 
        usuario_id: int, 
        offset: int = 0, 
        limit: int = 20
    ) -> List[Pedido]:
        """Obtiene el historial de pedidos de un usuario."""
        return self.uow.pedidos.get_by_usuario_id(usuario_id, offset, limit)
    
    def get_all_pedidos_admin(
        self,
        estado_id: Optional[int] = None,
        offset: int = 0,
        limit: int = 20
    ) -> List[Pedido]:
        """Obtiene todos los pedidos (vista administrador)."""
        return self.uow.pedidos.get_all_admin(estado_id, offset, limit)
    
    # Mapa de transiciones válidas
    TRANSICIONES_VALIDAS = {
        EstadoPedidoEnum.PENDIENTE: [EstadoPedidoEnum.CONFIRMADO, EstadoPedidoEnum.CANCELADO],
        EstadoPedidoEnum.CONFIRMADO: [EstadoPedidoEnum.EN_PREP, EstadoPedidoEnum.CANCELADO],
        EstadoPedidoEnum.EN_PREP: [EstadoPedidoEnum.EN_CAMINO],
        EstadoPedidoEnum.EN_CAMINO: [EstadoPedidoEnum.ENTREGADO],
        EstadoPedidoEnum.ENTREGADO: [],  # Estado terminal
        EstadoPedidoEnum.CANCELADO: []   # Estado terminal
    }
    def cambiar_estado_pedido(
        self, 
        pedido_id: int, 
        cambio: CambioEstadoRequest,
        usuario_cambio_id: Optional[int] = None
    ) -> Pedido: 
        """
        Cambia el estado de un pedido validando la máquina de estados.
        REGLAS:
        - solo INSERTs, nunca UPDATE/DELETE
        - Se registra quién hizo el cambio y cuándo
        """
        try: 
            with self.uow:
                pedido = self.uow.pedidos.get(pedido_id)
                if not pedido or pedido.deleted_at is not None:
                    raise HTTPException(
                        status_code = status.HTTP_404_NOT_FOUND,
                        detail = "Pedido no encontrado"
                    )
                # Obtener estado actual y nuevo estado
                estado_actual = self.uow.estados.get(pedido.estado_id)
                nuevo_estado = self.uow.estados.get_by_codigo(cambio.nuevo_estado)
                
                if not nuevo_estado:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"Estado '{cambio.nuevo_estado.value}' no existe"
                    )
                
                # VALIDAR TRANSICIÓN
                if nuevo_estado.codigo not in self.TRANSICIONES_VALIDAS.get(estado_actual.codigo, []):
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail=f"Transición inválida: de '{estado_actual.codigo.value}' no se puede ir a '{nuevo_estado.codigo.value}'. "
                               f"Estados permitidos: {[e.value for e in self.TRANSICIONES_VALIDAS.get(estado_actual.codigo, [])]}"
                    )
                
                # Aplicar nuevo estado
                pedido.estado_id = nuevo_estado.id
                pedido.updated_at = datetime.now(timezone.utc)
                self.uow.pedidos.update(pedido.id, pedido)
                
                # Registrar cambio en el historial)
                self._registrar_cambio_estado(
                    pedido_id=pedido.id,
                    nuevo_estado=cambio.nuevo_estado,
                    usuario_cambio_id=usuario_cambio_id,
                    observaciones=cambio.observaciones
                )
                
                # COMMIT automático
                return pedido
        except HTTPException:
            self.session.rollback()
            raise
        except Exception as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al cambiar estado: {str(e)}"
            )
            
    def _registrar_cambio_estado(
        self,
        pedido_id: int,
        nuevo_estado: EstadoPedidoEnum,
        usuario_cambio_id: Optional[int] = None,
        observaciones: Optional[str] = None
    ) -> None:
        """
        Método interno para registrar un cambio de estado en el historial.
        """
        estado = self.uow.estados.get_by_codigo(nuevo_estado)
        
        historial = HistorialEstadoPedido(
            pedido_id=pedido_id,
            estado_id=estado.id,
            usuario_cambio_id=usuario_cambio_id,
            observaciones=observaciones
        )
        self.uow.historial.create(historial)
        
    def cancelar_pedido(self, pedido_id: int, usuario_id: int) -> Pedido:
        """
        Permite a un cliente cancelar su propio pedido.
        Solo se puede cancelar desde PENDIENTE o CONFIRMADO.
        """
        
        pedido = self.get_pedido_by_id(pedido_id, usuario_id)
        estado_actual = self.uow.estados.get(pedido.estado_id)
        
        if estado_actual.codigo not in [EstadoPedidoEnum.PENDIENTE, EstadoPedidoEnum.CONFIRMADO]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"El pedido no puede ser cancelado desde el estado '{estado_actual.codigo.value}'"
            )
        
        # Usar el método genérico de cambio de estado
        cambio = CambioEstadoRequest(
            nuevo_estado=EstadoPedidoEnum.CANCELADO,
            observaciones="Cancelado por el cliente"
        )
        return self.cambiar_estado_pedido(pedido_id, cambio, usuario_cambio_id=usuario_id)
    
    def update_pedido(self, pedido_id: int, pedido_in: PedidoUpdate, usuario_id: int) -> Pedido:
        """
        Actualiza campos editables de un pedido.
        Solo se permite antes de que esté en preparación.
        """
        try: 
            with self.uow:
                pedido = self.get_pedido_by_id(pedido_id, usuario_id)
                
                #no permitir adicion si ya esta en preparacion o posterior
                estado_actual = self.uow.estados.get(pedido.estado_id)
                if estado_actual.orden >= 3: #en preparacion o posterior
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        DETAIL="No se puede modificar un pedido que ya está en preparacion"
                    )
                
                #Actualizar campos 
                update_data = pedido_in.model_dump(exclude_unset=True)
                for field, value in update_data.items():
                    if value is not None:
                        setattr(pedido, field, value)
                pedido.updated_at = datetime.now(timezone.utc)
                self.uow.pedidos.update(pedido.id, pedido)
                return pedido
            
        except HTTPException:
            self.session.rollback()
            raise
        except Exception as e:
            self.session.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Error al actualizar pedido: {str(e)}"
            )
                    
