from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Annotated, Optional, List
from sqlmodel import Session
from app.core.database import get_session
from app.core.deps import get_current_active_user, require_role
from app.modules.user.models import User
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
    tags=["Pedidos"],
    responses={
        401: {"description": "No autenticado"},
        403: {"description": "Acceso denegado"},
        404: {"description": "Recurso no encontrado"},
        409: {"description": "Conflicto de negocio"}
    }
)


def get_pedido_service(session: Session = Depends(get_session)) -> PedidoService:
    """Factory de dependencia: inyecta el servicio con su Session."""
    return PedidoService(session)



@router.post(
    "/",
    response_model=PedidoPublic,
    status_code=status.HTTP_201_CREATED,
    summary="Crear nuevo pedido",
    description="Crea un pedido desde el carrito. Transacción: descuenta stock, crea pedido y detalles, registra estado inicial."
)
def create_pedido(
    pedido_in: PedidoCreate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    svc: PedidoService = Depends(get_pedido_service)
) -> PedidoPublic:
    """
    Al menos un producto en el carrito
    Stock disponible para cada producto
    Cálculo automático de totales
    """
    return svc.crear_pedido(usuario_id=current_user.id, pedido_in=pedido_in)


@router.get(
    "/estados",
    response_model=List[EstadoPedidoPublic],
    summary="Listar estados de pedido disponibles",
    description="Obtiene la lista de estados posibles para mostrar en la UI."
)
def list_estados_pedido(
    svc: PedidoService = Depends(get_pedido_service)
) -> List[EstadoPedidoPublic]:
    """
    Cualquiera puede consultar los estados disponibles.
    Se ordenan por el campo 'orden' para mostrar en secuencia lógica.
    """
    return svc.get_estados_pedido_ordered()


@router.get(
    "/admin/",
    response_model=PedidoList,
    summary="[ADMIN] Listar todos los pedidos",
    description="Vista administrativa: lista todos los pedidos del sistema con filtros y paginación."
)
def admin_list_pedidos(
    _admin: Annotated[User, Depends(require_role(["ADMIN", "PEDIDOS"]))],
    svc: PedidoService = Depends(get_pedido_service),
    estado_id: Optional[int] = Query(default=None, description="Filtrar por ID de estado"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100)
) -> PedidoList:
    """
    Filtrado opcional por estado_id.
    Paginación con offset/limit.
    Solo administradores y personal de pedidos pueden acceder.
    """
    pedidos = svc.get_all_pedidos_admin(
        estado_id=estado_id,
        offset=offset,
        limit=limit
    )
    total = svc.count_pedidos_admin(estado_id)
    return PedidoList(data=pedidos, total=total)


@router.get(
    "/",
    response_model=PedidoList,
    summary="Listar mis pedidos",
    description="Obtiene el historial de pedidos del usuario con paginación."
)
def list_mis_pedidos(
    current_user: Annotated[User, Depends(get_current_active_user)],
    svc: PedidoService = Depends(get_pedido_service),
    offset: int = Query(default=0, ge=0, description="Offset para paginación"),
    limit: int = Query(default=20, ge=1, le=100, description="Límite de resultados (máx 100)")
) -> PedidoList:
    """LISTADO PARA CLIENTE: Solo ve sus propios pedidos."""
    pedidos = svc.get_pedidos_by_usuario(
        usuario_id=current_user.id,
        offset=offset,
        limit=limit
    )
    total = svc.count_pedidos_by_usuario(current_user.id)
    return PedidoList(data=pedidos, total=total)


@router.get(
    "/{pedido_id}",
    response_model=PedidoPublic,
    summary="Obtener detalle de pedido",
    description="Obtiene un pedido específico por ID."
)
def get_pedido(
    pedido_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    svc: PedidoService = Depends(get_pedido_service)
) -> PedidoPublic:
    """
    CLIENTE: Solo puede ver sus propios pedidos
    ADMIN/PEDIDOS: Pueden ver cualquier pedido
    """
    # Determinar si es admin o PEDIDOS basado en los roles del token
    user_roles: list[str] = getattr(current_user, "_roles_from_token", [])
    es_admin = "ADMIN" in user_roles or "PEDIDOS" in user_roles
    return svc.get_pedido_by_id(
        pedido_id=pedido_id,
        usuario_id=current_user.id,
        es_admin=es_admin
    )


@router.get(
    "/{pedido_id}/historial",
    response_model=List[HistorialEstadoPedidoPublic],
    summary="Historial de estados del pedido",
    description="Obtiene el audit trail completo de cambios de estado de un pedido."
)
def get_pedido_historial(
    pedido_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    svc: PedidoService = Depends(get_pedido_service)
) -> List[HistorialEstadoPedidoPublic]:
    """Solo el dueño del pedido o roles ADMIN/PEDIDOS pueden consultarlo."""
    # Determinar si es admin o PEDIDOS basado en los roles del token
    user_roles: list[str] = getattr(current_user, "_roles_from_token", [])
    es_admin = "ADMIN" in user_roles or "PEDIDOS" in user_roles
    # Validar acceso al pedido primero
    svc.get_pedido_by_id(pedido_id, usuario_id=current_user.id, es_admin=es_admin)
    # Retornar historial
    return svc.get_historial_estados(pedido_id)


@router.post(
    "/{pedido_id}/cancelar",
    response_model=PedidoPublic,
    summary="Cancelar pedido",
    description="Permite al cliente cancelar su propio pedido si está en estado PENDIENTE o CONFIRMADO."
)
def cancelar_pedido(
    pedido_id: int,
    current_user: Annotated[User, Depends(get_current_active_user)],
    svc: PedidoService = Depends(get_pedido_service)
) -> PedidoPublic:
    """
    Solo desde estados PENDIENTE o CONFIRMADO.
    Reintegra stock automáticamente (manejado en el service).
    Registra el cambio en el audit trail.
    """
    return svc.cancelar_pedido(pedido_id=pedido_id, usuario_id=current_user.id)



@router.patch(
    "/{pedido_id}/estado",
    response_model=PedidoPublic,
    summary="[ADMIN/PEDIDOS] Cambiar estado del pedido",
    description="Avanza o modifica el estado de un pedido validando la máquina de estados."
)
def update_pedido_estado(
    pedido_id: int,
    cambio: CambioEstadoRequest,
    admin_user: Annotated[User, Depends(require_role(["ADMIN", "PEDIDOS"]))],
    svc: PedidoService = Depends(get_pedido_service)
) -> PedidoPublic:
    """
    Valida transiciones permitidas
    Registra quién hizo el cambio y cuándo
    Solo administradores y personal de pedidos pueden cambiar el estado.
    """
    return svc.cambiar_estado_pedido(
        pedido_id=pedido_id,
        cambio=cambio,
        usuario_cambio_id=admin_user.id
    )


@router.patch(
    "/{pedido_id}",
    response_model=PedidoPublic,
    summary="Actualizar datos editables del pedido",
    description="Permite modificar notas, dirección o forma de pago antes de que entre en preparación."
)
def update_pedido(
    pedido_id: int,
    pedido_in: PedidoUpdate,
    current_user: Annotated[User, Depends(get_current_active_user)],
    svc: PedidoService = Depends(get_pedido_service)
) -> PedidoPublic:
    """
    Solo campos no críticos: notas, dirección, forma de pago.
    No permitido si el pedido ya está EN_PREP o posterior.
    Solo el dueño del pedido puede editar.
    """
    return svc.update_pedido(
        pedido_id=pedido_id,
        pedido_in=pedido_in,
        usuario_id=current_user.id
    )