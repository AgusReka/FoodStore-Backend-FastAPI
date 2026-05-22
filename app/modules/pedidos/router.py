from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional, List
from sqlmodel import Session
from app.core.database import get_session
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
    svc: PedidoService = Depends(get_pedido_service),
    usuario_id: int = Query(default=1, description="ID de usuario simulado")
) -> PedidoPublic:
    """
    Al menos un producto en el carrito
    Stock disponible para cada producto
    Cálculo automático de totales
    """
    return svc.crear_pedido(usuario_id=usuario_id, pedido_in=pedido_in)


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
    "/",
    response_model=PedidoList,
    summary="Listar mis pedidos",
    description="Obtiene el historial de pedidos del usuario con paginación."
)
def list_mis_pedidos(
    svc: PedidoService = Depends(get_pedido_service),
    usuario_id: int = Query(default=1, description="ID de usuario simulado"),
    offset: int = Query(default=0, ge=0, description="Offset para paginación"),
    limit: int = Query(default=20, ge=1, le=100, description="Límite de resultados (máx 100)")
) -> PedidoList:
    """LISTADO PARA CLIENTE: Solo ve sus propios pedidos."""
    pedidos = svc.get_pedidos_by_usuario(
        usuario_id=usuario_id,
        offset=offset,
        limit=limit
    )
    total = svc.count_pedidos_by_usuario(usuario_id)
    return PedidoList(data=pedidos, total=total)


@router.get(
    "/{pedido_id}",
    response_model=PedidoPublic,
    summary="Obtener detalle de pedido",
    description="Obtiene un pedido específico por ID."
)
def get_pedido(
    pedido_id: int,
    svc: PedidoService = Depends(get_pedido_service),
    usuario_id: int = Query(default=1, description="ID de usuario simulado"),
    es_admin: bool = Query(default=True, description="Simular si es admin (puede ver cualquier pedido)")
) -> PedidoPublic:
    """
    CLIENTE: Solo puede ver sus propios pedidos
    ADMIN/PEDIDOS: Pueden ver cualquier pedido (es_admin=True)
    """
    return svc.get_pedido_by_id(
        pedido_id=pedido_id,
        usuario_id=usuario_id,
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
    svc: PedidoService = Depends(get_pedido_service),
    usuario_id: int = Query(default=1, description="ID de usuario simulado"),
    es_admin: bool = Query(default=True, description="Simular si es admin")
) -> List[HistorialEstadoPedidoPublic]:
    """Solo el dueño del pedido o roles con permiso pueden consultarlo."""
    # Validar acceso al pedido primero
    svc.get_pedido_by_id(pedido_id, usuario_id=usuario_id, es_admin=es_admin)
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
    svc: PedidoService = Depends(get_pedido_service),
    usuario_id: int = Query(default=1, description="ID de usuario simulado")
) -> PedidoPublic:
    """
    Solo desde estados PENDIENTE o CONFIRMADO.
    Reintegra stock automáticamente (manejado en el service).
    Registra el cambio en el audit trail.
    """
    return svc.cancelar_pedido(pedido_id=pedido_id, usuario_id=usuario_id)



@router.get(
    "/admin/",
    response_model=PedidoList,
    summary="[ADMIN] Listar todos los pedidos",
    description="Vista administrativa: lista todos los pedidos del sistema con filtros y paginación."
)
def admin_list_pedidos(
    svc: PedidoService = Depends(get_pedido_service),
    estado_id: Optional[int] = Query(default=None, description="Filtrar por ID de estado"),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100)
) -> PedidoList:
    """
    Filtrado opcional por estado_id.
    Paginación con offset/limit.
    Simula acceso de ADMIN.
    """
    pedidos = svc.get_all_pedidos_admin(
        estado_id=estado_id,
        offset=offset,
        limit=limit
    )
    total = svc.count_pedidos_admin(estado_id)
    return PedidoList(data=pedidos, total=total)


@router.patch(
    "/{pedido_id}/estado",
    response_model=PedidoPublic,
    summary="[ADMIN/PEDIDOS] Cambiar estado del pedido",
    description="Avanza o modifica el estado de un pedido validando la máquina de estados."
)
def update_pedido_estado(
    pedido_id: int,
    cambio: CambioEstadoRequest,
    svc: PedidoService = Depends(get_pedido_service),
    usuario_cambio_id: int = Query(default=1, description="ID del admin que realiza el cambio")
) -> PedidoPublic:
    """
    Valida transiciones permitidas
    Registra quién hizo el cambio y cuánd
    """
    return svc.cambiar_estado_pedido(
        pedido_id=pedido_id,
        cambio=cambio,
        usuario_cambio_id=usuario_cambio_id
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
    svc: PedidoService = Depends(get_pedido_service),
    usuario_id: int = Query(default=1, description="ID de usuario simulado")
) -> PedidoPublic:
    """
    Solo campos no críticos: notas, dirección, forma de pago.
    No permitido si el pedido ya está EN_PREP o posterior.
    Solo el dueño del pedido puede editar.
    """
    return svc.update_pedido(
        pedido_id=pedido_id,
        pedido_in=pedido_in,
        usuario_id=usuario_id
    )