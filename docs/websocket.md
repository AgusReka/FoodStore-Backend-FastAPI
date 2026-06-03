# WebSocket de Pedidos — Tiempo real

Canal **en tiempo real** para pedidos. Evita el *polling* (consultar la API cada X
segundos) y sirve a dos tipos de usuarios:

- **Staff** (`COCINA`, `PEDIDOS`, `ADMIN`): recibe automáticamente los pedidos que le
  tocan según su rol, como una "cola de trabajo" viva.
- **Cliente**: sigue el estado de **sus propios pedidos** en vivo
  (ej. `PENDIENTE → CONFIRMADO → EN_PREP → LISTO`).

Implementación:

- Infraestructura (`ConnectionManager`): `app/core/websocket.py`
- Endpoint: `app/modules/pedidos/router.py` (`@router.websocket("/ws")`)
- Notificaciones: `app/modules/pedidos/service.py` (al crear o cambiar estado de un pedido)

---

## Cómo conectarse

**URL:** `ws://localhost:8000/api/v1/pedidos/ws`

> Se forma con el prefijo del router (`/api/v1/pedidos`, en `main.py`) + la ruta `/ws`.

**Autenticación:** vía la cookie HttpOnly `access_token` (la misma del login). El handshake:

1. Lee el token de la cookie `access_token`. Si no hay → cierra con código `1008`.
2. Decodifica y valida el JWT (firma + expiración). Inválido → cierra `1008`.
3. Valida que el usuario exista en la BD y no esté deshabilitado → si no, cierra `1008`.
4. Une el socket a una *room* por cada rol staff que tenga el token.

```js
// Primero hacés login (POST /api/v1/auth/...) → setea la cookie access_token.
// Conectá desde el mismo origen/navegador para que la cookie viaje sola.
const ws = new WebSocket("ws://localhost:8000/api/v1/pedidos/ws");

ws.onopen    = () => console.log("conectado");
ws.onmessage = (e) => console.log("evento:", JSON.parse(e.data));
ws.onclose   = (e) => console.log("cerrado:", e.code, e.reason);
```

> ⚠️ Como la auth depende de una **cookie de navegador**, herramientas tipo Postman /
> `wscat` necesitan que les pases manualmente la cookie (`Cookie: access_token=<jwt>`),
> porque no hacen el login automáticamente.

---

## Rooms (canales internos)

El `ConnectionManager` agrupa los sockets en dos tipos de rooms:

| Room          | Quién está                        | Para qué                  |
|---------------|-----------------------------------|---------------------------|
| `role:{ROL}`  | sockets de staff con ese rol      | cola de trabajo del rol   |
| `order:{id}`  | el cliente dueño de ese pedido    | seguir un pedido puntual  |

---

## Acciones del cliente (cliente → servidor)

Mensajes de texto en JSON. Solo aplican a clientes (el staff no las necesita):

```js
// Suscribirse a un pedido propio
ws.send(JSON.stringify({ action: "subscribe-order", order_id: 42 }));

// Dejar de seguirlo
ws.send(JSON.stringify({ action: "unsubscribe-order", order_id: 42 }));
```

Al suscribirse, el server valida la **propiedad del pedido** reutilizando el `PedidoService`:

- Si el pedido es tuyo → `{"event": "SUBSCRIBED", "data": {"order_id": 42}}`
- Si no es tuyo / no existe → `{"event": "ERROR", "data": {"detail": "..."}}`

---

## Eventos (servidor → cliente)

| Evento            | A quién llega                                                | Cuándo                              |
|-------------------|--------------------------------------------------------------|-------------------------------------|
| `NUEVO_PEDIDO`    | staff del rol que gestiona el estado inicial                 | se crea un pedido                   |
| `PEDIDO_ENTRANTE` | staff del rol que gestiona el **nuevo** estado               | cambio de estado                    |
| `PEDIDO_REMOVIDO` | staff que gestionaba el estado **anterior** (y ya no el nuevo) | cambio de estado (sale de su cola) |
| `PEDIDO_ESTADO`   | cliente suscripto a `order:{id}`                             | cualquier cambio de estado del pedido |
| `SUBSCRIBED` / `ERROR` | el cliente que pidió suscribirse                        | respuesta a `subscribe-order`       |

`NUEVO_PEDIDO`, `PEDIDO_ENTRANTE` y `PEDIDO_ESTADO` traen el pedido completo
(`PedidoPublic`) en `data`. `PEDIDO_REMOVIDO` trae un payload liviano:
`{pedido_id, estado_nuevo}`.

> Las notificaciones se emiten **después** de que la transacción commitea, así un cliente
> que recibe el evento y consulta el pedido por HTTP siempre lo encuentra ya guardado.

---

## Cómo funciona la parte de roles 🎯

Hay tres roles staff con cola propia (`STAFF_ROLES`):

```
ADMIN · PEDIDOS · COCINA
```

**Regla central:** un rol *gestiona* un estado si tiene permitida alguna transición
**que sale de** ese estado. Esto está persistido en la tabla `transicion_estado` y se
consulta con `roles_por_estado_origen(estado_id)`.

> En criollo: si tu rol puede mover un pedido a partir del estado X, entonces el estado X
> es "tu cola" y se te notifica cuando un pedido cae ahí.

Flujo al notificar (`_build_notificaciones` en `service.py`):

1. **Pedido entra a un estado** → se busca qué roles operan desde ese estado y se les manda
   `NUEVO_PEDIDO` / `PEDIDO_ENTRANTE` con el pedido completo (les apareció trabajo).
2. **Pedido sale de un estado** → a los roles que gestionaban el estado viejo y **ya no**
   gestionan el nuevo, se les manda `PEDIDO_REMOVIDO` (sáquenlo de su cola).
3. **Siempre** → al cliente dueño (room `order:{id}`) le llega `PEDIDO_ESTADO`.

Ejemplo de flujo (depende de cómo esté cargada `transicion_estado`):

- Cliente crea pedido → estado `PENDIENTE`. Los roles que operan desde PENDIENTE
  (ej. `PEDIDOS`) reciben `NUEVO_PEDIDO`.
- `PEDIDOS` lo pasa a `CONFIRMADO` → quien opere desde CONFIRMADO recibe `PEDIDO_ENTRANTE`;
  si `PEDIDOS` ya no gestiona el nuevo estado, recibe `PEDIDO_REMOVIDO`. El cliente recibe
  `PEDIDO_ESTADO`.
- `COCINA` pasa de `EN_PREP` a `LISTO`, etc.

Quién puede ejecutar cada transición se valida aparte en `cambiar_estado_pedido` con
`roles_permitidos(origen, destino)`: si tu rol no tiene esa transición, devuelve `403`/`409`.

> **Importante:** los clientes (rol no-staff) **no** se unen a ninguna room `role:` —
> solo pueden seguir pedidos propios vía `subscribe-order`.

---

## Códigos de cierre

| Código | Motivo                                                |
|--------|-------------------------------------------------------|
| `1008` | Falta token, token inválido/expirado, o usuario inactivo |
