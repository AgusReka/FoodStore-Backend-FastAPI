"""
Infraestructura de WebSocket en tiempo real para pedidos.

`ConnectionManager` administra las conexiones activas agrupadas en *rooms*:

    role:{ROL}   → todos los sockets de un rol staff (ADMIN, PEDIDOS, COCINA)
    order:{id}   → sockets (clientes) suscriptos a un pedido puntual

Puente sync → async:
    El resto del proyecto es síncrono (services, repos y endpoints HTTP son
    `def`, ejecutados por Starlette en un threadpool). Los broadcasts a los
    WebSockets, en cambio, viven en el event loop principal. Por eso el manager
    guarda una referencia al loop (`bind_loop`) y expone `notify`/`notify_roles`
    síncronos que agendan el broadcast con `run_coroutine_threadsafe`.
    Si no hay loop ni conexiones, las notificaciones son un no-op barato.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Iterable, Optional

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        # room → sockets en esa room
        self.rooms: dict[str, set[WebSocket]] = {}
        # socket → rooms a las que pertenece (para limpiar al desconectar)
        self.socket_rooms: dict[WebSocket, set[str]] = {}
        # Event loop principal donde corren los broadcasts (se setea al arrancar)
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ── Ciclo de vida del loop ───────────────────────────────────────────────
    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Guarda el event loop principal. Idempotente."""
        self._loop = loop

    # ── Conexión / desconexión ───────────────────────────────────────────────
    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self.socket_rooms.setdefault(websocket, set())

    def disconnect(self, websocket: WebSocket) -> None:
        """Saca el socket de todas sus rooms y lo olvida."""
        rooms = self.socket_rooms.pop(websocket, set())
        for room in rooms:
            members = self.rooms.get(room)
            if members:
                members.discard(websocket)
                if not members:
                    self.rooms.pop(room, None)

    # ── Manejo de rooms ──────────────────────────────────────────────────────
    def _join_room(self, websocket: WebSocket, room: str) -> None:
        self.rooms.setdefault(room, set()).add(websocket)
        self.socket_rooms.setdefault(websocket, set()).add(room)

    def _leave_room(self, websocket: WebSocket, room: str) -> None:
        members = self.rooms.get(room)
        if members:
            members.discard(websocket)
            if not members:
                self.rooms.pop(room, None)
        self.socket_rooms.get(websocket, set()).discard(room)

    def join_role_room(self, websocket: WebSocket, rol: str) -> None:
        self._join_room(websocket, f"role:{rol}")

    def join_order_room(self, websocket: WebSocket, order_id: int) -> None:
        self._join_room(websocket, f"order:{order_id}")

    def leave_order_room(self, websocket: WebSocket, order_id: int) -> None:
        self._leave_room(websocket, f"order:{order_id}")

    # ── Broadcast (async, corre en el event loop) ────────────────────────────
    async def broadcast(self, room: str, message: dict) -> None:
        """Envía `message` a todos los sockets de una room, tolerando caídos."""
        members = list(self.rooms.get(room, set()))
        for websocket in members:
            try:
                await websocket.send_json(message)
            except Exception:
                # Socket muerto o a medio cerrar → limpiarlo
                self.disconnect(websocket)

    # ── Puente sync → async ──────────────────────────────────────────────────
    def notify(self, room: str, message: dict) -> None:
        """Agenda un broadcast desde código síncrono (endpoints/services)."""
        if self._loop is None:
            return
        if not self.rooms.get(room):
            return
        try:
            asyncio.run_coroutine_threadsafe(
                self.broadcast(room, message), self._loop
            )
        except Exception:
            logger.exception("No se pudo agendar el broadcast a %s", room)

    def notify_roles(self, roles: Iterable[str], message: dict) -> None:
        """Notifica el mismo mensaje a las rooms `role:{ROL}` indicadas."""
        for rol in roles:
            self.notify(f"role:{rol}", message)


# Singleton de módulo, compartido por endpoints y services
manager = ConnectionManager()
