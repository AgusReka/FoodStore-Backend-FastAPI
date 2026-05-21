from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Annotated, Optional, List
from sqlmodel import Session
#from app.core.database import get_db
#from app.core.dependencies import get_current_user, require_role
#from app.modules.usuario.models import Usuario
from app.modules.pedidos.service import PedidoService
from app.modules.pedidos.schemas import (
    PedidoCreate,
    PedidoUpdate,
    PedidoPublic,
    PedidoList,
    CambioEstadoRequest,
    HistorialEstadoPedidoPublic,
    EstadoPedidoPublic,
    EstadoPedidoEnum
)

router = APIRouter(
    prefix="/pedidos",
    tags=["Pedidos"],
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Acceso denegado"},
        404: {"description": "Recurso no encontrado"},
        409: {"description": "Conflicto de negocio"}
    }
)

# @router.post(
#     "/",
#     response_model=PedidoPublic,
#     status_code=status.HTTP_201_CREATED,
#     summary="Crear nuevo pedido",
#     description="Crea un pedido desde el carrito. Transacción atómica: descuenta stock, crea pedido y detalles, registra estado inicial."
# )
# async def create_pedido(
#     pedido_in: PedidoCreate,
#     #current_user: Annotated[Usuario, Depends(get_current_user)],
#     db: Annotated[Session, Depends(get_db)]
# ) -> PedidoPublic:
#     """
#     Endpoint para que un CLIENTE cree un nuevo pedido.
#     Usuario autenticado
#     Al menos un producto en el carrito
#     Stock disponible para cada producto
#     Cálculo automático de totales
#     """
#     service = PedidoService(db)
#     #pedido = service.create_pedido(usuario_id=current_user.id, pedido_in=pedido_in)
#     return pedido

# @router.get(
#     "/",
#     response_model=PedidoList,
#     summary="Listar mis pedidos",
#     description="Obtiene el historial de pedidos del usuario autenticado con paginación."
# )
# async def list_mis_pedidos(
#     #current_user: Annotated[Usuario, Depends(get_current_user)],
#     db: Annotated[Session, Depends(get_db)],
#     offset: Annotated[int, Query(ge=0, description="Offset para paginación")] = 0,
#     limit: Annotated[int, Query(ge=1, le=100, description="Límite de resultados (máx 100)")] = 20
# ) -> PedidoList:
#     """
#     LISTADO PARA CLIENTE: Solo ve sus propios pedidos.
#     """
#     service = PedidoService(db)
#     pedidos = service.get_pedidos_by_usuario(
#         usuario_id=current_user.id,
#         offset=offset,
#         limit=limit
#     )
#     total = service.uow.pedidos.count_by_usuario(current_user.id)
    
#     return PedidoList(data=pedidos, total=total)

# @router.get(
#     "/{pedido_id}",
#     response_model=PedidoPublic,
#     summary="Obtener detalle de pedido",
#     description="Obtiene un pedido específico por ID. Solo el dueño o roles con permiso pueden verlo."
# )
# async def get_pedido(
#     pedido_id: int,
#     current_user: Annotated[Usuario, Depends(get_current_user)],
#     db: Annotated[Session, Depends(get_db)]
# ) -> PedidoPublic:
#     """
#     DETALLE DE PEDIDO:
#     - CLIENT: Solo puede ver sus propios pedidos
#     - ADMIN/PEDIDOS: Pueden ver cualquier pedido
#     """
#     # Verificar si es admin o gestor de pedidos para permitir acceso amplio
#     es_admin = False
#     try:
#         await require_role(["ADMIN", "PEDIDOS"])(current_user=current_user, db=db)
#         es_admin = True
#     except HTTPException:
#         pass  # No es admin, se validará en el service
    
#     service = PedidoService(db)
#     pedido = service.get_pedido_by_id(
#         pedido_id=pedido_id,
#         usuario_id=current_user.id,
#         es_admin=es_admin
#     )
#     return pedido

# @router.get(
#     "/{pedido_id}/historial",
#     response_model=List[HistorialEstadoPedidoPublic],
#     summary="Historial de estados del pedido",
#     description="Obtiene el audit trail completo de cambios de estado de un pedido."
# )
# async def get_pedido_historial(
#     pedido_id: int,
#     current_user: Annotated[Usuario, Depends(get_current_user)],
#     db: Annotated[Session, Depends(get_db)]
# ) -> List[HistorialEstadoPedidoPublic]:
#     """
#     Solo el dueño del pedido o roles con permiso pueden consultarlo.
#     """
#     es_admin = False
#     try:
#         await require_role(["ADMIN", "PEDIDOS"])(current_user=current_user, db=db)
#         es_admin = True
#     except HTTPException:
#         pass
    
#     service = PedidoService(db)
#     # Validar acceso al pedido primero
#     service.get_pedido_by_id(pedido_id, usuario_id=current_user.id, es_admin=es_admin)
    
#     # Retornar historial
#     historial = service.get_historial_estados(pedido_id)
#     return historial

# @router.post(
#     "/{pedido_id}/cancelar",
#     response_model=PedidoPublic,
#     summary="Cancelar pedido",
#     description="Permite al cliente cancelar su propio pedido si está en estado PENDIENTE o CONFIRMADO."
# )
# async def cancelar_pedido(
#     pedido_id: int,
#     current_user: Annotated[Usuario, Depends(get_current_user)],
#     db: Annotated[Session, Depends(get_db)]
# ) -> PedidoPublic:
#     """
#     Solo desde estados PENDIENTE o CONFIRMADO
#     Reintegra stock automáticamente (manejado en el service)
#     Registra el cambio en el audit trail
#     """
#     service = PedidoService(db)
#     pedido = service.cancelar_pedido(pedido_id=pedido_id, usuario_id=current_user.id)
#     return pedido

# @router.get(
#     "/admin/",
#     response_model=PedidoList,
#     summary="[ADMIN] Listar todos los pedidos",
#     description="Vista administrativa: lista todos los pedidos del sistema con filtros y paginación."
# )
# async def admin_list_pedidos(
#     current_user: Annotated[Usuario, Depends(lambda: require_role(["ADMIN", "PEDIDOS"]))],
#     db: Annotated[Session, Depends(get_db)],
#     estado_id: Annotated[Optional[int], Query(description="Filtrar por ID de estado")] = None,
#     offset: Annotated[int, Query(ge=0)] = 0,
#     limit: Annotated[int, Query(ge=1, le=100)] = 20
# ) -> PedidoList:
#     """
#     Filtrado opcional por estado_id
#     Paginación con offset/limit
#     Solo accesible para ADMIN y EMPLEADOS
#     """
#     service = PedidoService(db)
#     pedidos = service.get_all_pedidos_admin(
#         estado_id=estado_id,
#         offset=offset,
#         limit=limit
#     )
#     total = service.uow.pedidos.count_admin(estado_id)
    
#     return PedidoList(data=pedidos, total=total)

# @router.patch(
#     "/{pedido_id}/estado",
#     response_model=PedidoPublic,
#     summary="[ADMIN/PEDIDOS] Cambiar estado del pedido",
#     description="Avanza o modifica el estado de un pedido validando la máquina de estados."
# )
# async def update_pedido_estado(
#     pedido_id: int,
#     cambio: CambioEstadoRequest,
#     current_user: Annotated[Usuario, Depends(lambda: require_role(["ADMIN", "PEDIDOS"]))],
#     db: Annotated[Session, Depends(get_db)]
# ) -> PedidoPublic:
#     """
#     Valida transiciones permitidas (ej: PENDIENTE → CONFIRMADO ✓, PENDIENTE → ENTREGADO ✗)
#     Registra quién hizo el cambio y cuándo (audit trail)
#     Solo ADMIN y PEDIDOS pueden ejecutar esta acción
#     """
#     service = PedidoService(db)
#     pedido = service.cambiar_estado_pedido(
#         pedido_id=pedido_id,
#         cambio=cambio,
#         usuario_cambio_id=current_user.id
#     )
#     return pedido

# @router.patch(
#     "/{pedido_id}",
#     response_model=PedidoPublic,
#     summary="Actualizar datos editables del pedido",
#     description="Permite modificar notas, dirección o forma de pago antes de que entre en preparación."
# )
# async def update_pedido(
#     pedido_id: int,
#     pedido_in: PedidoUpdate,
#     current_user: Annotated[Usuario, Depends(get_current_user)],
#     db: Annotated[Session, Depends(get_db)]
# ) -> PedidoPublic:
#     """
#     Solo campos no críticos: notas, dirección, forma de pago
#     No permitido si el pedido ya está EN_PREP o posterior
#     Solo el dueño del pedido puede editar
#     """
#     service = PedidoService(db)
#     pedido = service.update_pedido(
#         pedido_id=pedido_id,
#         pedido_in=pedido_in,
#         usuario_id=current_user.id
#     )
#     return pedido

# @router.get(
#     "/estados",
#     response_model=List[EstadoPedidoPublic],
#     summary="Listar estados de pedido disponibles",
#     description="Obtiene la lista de estados posibles para mostrar en la UI."
# )
# async def list_estados_pedido(
#     db: Annotated[Session, Depends(get_db)]
# ) -> List[EstadoPedidoPublic]:
#     """
#     Cualquiera puede consultar los estados disponibles.
#     Se ordenan por el campo 'orden' para mostrar en secuencia lógica.
#     """
#     service = PedidoService(db)
#     return service.uow.estados.get_all_ordered()