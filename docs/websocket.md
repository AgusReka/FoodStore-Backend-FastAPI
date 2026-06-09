# WebSocket de Pedidos — Tiempo real

Canal **en tiempo real** para pedidos. Evita el *polling* (consultar la API cada X
segundos) y sirve a dos tipos de usuarios:

- **Staff** (`COCINA`, `PEDIDOS`, `ADMIN`): recibe automáticamente los pedidos que su rol
  **ve**, como un tablero de trabajo vivo (ver [Visibilidad por rol](#visibilidad-por-rol-)).
- **Cliente**: sigue el estado de **sus propios pedidos** en vivo
  (ej. `PENDIENTE → CONFIRMADO → EN_PREP → LISTO`).

Implementación:

- Infraestructura (`ConnectionManager`): `app/core/websocket.py`
- Endpoint WS + `GET /cola`: `app/modules/pedidos/router.py`
- Visibilidad + notificaciones: `app/modules/pedidos/service.py` (`ROLE_VISIBILITY`,
  `_build_notificaciones`, al crear/cambiar estado de un pedido)

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

| Evento            | A quién llega                                                  | Cuándo                                |
|-------------------|---------------------------------------------------------------|---------------------------------------|
| `UPSERT`          | staff cuyo rol **ve** el **nuevo** estado                     | se crea un pedido / cambio de estado  |
| `REMOVE`          | staff cuyo rol **veía** el estado anterior (y ya no el nuevo) | cambio de estado (sale de su tablero) |
| `PEDIDO_ESTADO`   | cliente suscripto a `order:{id}`                              | cualquier cambio de estado del pedido |
| `SUBSCRIBED` / `ERROR` | el cliente que pidió suscribirse                          | respuesta a `subscribe-order`         |

> "Ve" se define por **visibilidad por rol** (ver sección más abajo), no por qué transiciones
> puede ejecutar el rol. El front ubica cada pedido en su sección según `data.estado_codigo`.

**Shape único** — todos los eventos comparten la misma estructura, con el pedido completo
(`PedidoPublic`) en `data` (incluido `REMOVE`):

```json
{ "event": "UPSERT", "id": 42, "data": { /* PedidoPublic completo */ } }
```

Así el front mantiene sus listas por `id`:

- `UPSERT` → agregar el pedido a la lista, o reemplazarlo si ya estaba (match por `id`).
- `REMOVE` → quitar de la lista el pedido con ese `id`.
- `PEDIDO_ESTADO` → el cliente actualiza el estado del pedido que está siguiendo.

> Las notificaciones se emiten **después** de que la transacción commitea, así un cliente
> que recibe el evento y consulta el pedido por HTTP siempre lo encuentra ya guardado.

---

## Lista inicial (tablero por rol) 📋

El WS **solo informa cambios**; no manda la foto inicial. El flujo recomendado para el staff:

1. Al entrar, traer la lista inicial con **`GET /api/v1/pedidos/cola`**: devuelve un
   `PedidoList` (`{data: [...], total}`) con los pedidos que el **rol del usuario ve**
   (según el mapa de visibilidad de abajo).
2. Conectarse al WebSocket y, de ahí en más, **solo modificar esa lista** con los eventos:
   `UPSERT` (agregar/actualizar por `id`) y `REMOVE` (borrar por `id`).
3. El front **separa la lista en secciones** mirando `estado_codigo` de cada pedido (ver
   ejemplo del cajero abajo). No hace falta otra llamada HTTP.

`/cola` usa la **misma fuente de verdad** (`ROLE_VISIBILITY`) que rutea el WS, así la lista
inicial y los eventos quedan siempre consistentes. Acceso: ADMIN, PEDIDOS, COCINA.
Parámetros: `offset` (≥0) y `limit` (1–100, default 50).

> Los estados terminales (`CANCELADO`, `ENTREGADO`) en `/cola` vienen **acotados a las
> últimas 24h** (por `updated_at`). Por el WS, en cambio, toda cancelación/entrega recién
> ocurrida llega siempre (es reciente por definición).

---

## Visibilidad por rol 🎯

Hay que distinguir dos conceptos:

- **Operabilidad** — qué transiciones puede *ejecutar* un rol. Vive en `transicion_estado` y
  se valida en `cambiar_estado_pedido` con `roles_permitidos(origen, destino)` (si tu rol no
  tiene esa transición → `403`/`409`). **No** define qué ves.
- **Visibilidad** — qué estados quiere *ver* un rol en su tablero. Vive en `ROLE_VISIBILITY`
  (`app/modules/pedidos/service.py`) y alimenta **tanto `/cola` como el ruteo del WS**.

Mapa de visibilidad actual:

| Rol     | Estados que ve                                                           |
|---------|-------------------------------------------------------------------------|
| PEDIDOS | PENDIENTE, CONFIRMADO, EN_PREP, LISTO, CANCELADO (24h), ENTREGADO (24h)  |
| COCINA  | CONFIRMADO, EN_PREP                                                      |
| ADMIN   | PENDIENTE, CONFIRMADO, EN_PREP, LISTO, CANCELADO (24h), ENTREGADO (24h)  |

Ejemplo de **secciones del cajero** (PEDIDOS), todas reconstruibles desde `estado_codigo`:

- **Cola operable**: `PENDIENTE` (confirmar) y `LISTO` (entregar).
- **En cocina** (solo lectura): `CONFIRMADO`, `EN_PREP`.
- **Cancelados** (24h): `CANCELADO`.
- **Entregados** (24h): `ENTREGADO`.

La **cocina** solo ve `CONFIRMADO` y `EN_PREP`: nunca ve cancelados ni entregados.

Flujo al notificar (`_build_notificaciones` en `service.py`):

1. **Pedido entra a un estado** → a los roles que **ven** ese estado se les manda `UPSERT`
   con el pedido completo (agregar/actualizar en su lista; el front lo ubica por `estado_codigo`).
2. **Pedido sale de un estado** → a los roles que veían el estado viejo y **ya no** ven el
   nuevo, se les manda `REMOVE` (sáquenlo de su tablero).
3. **Siempre** → al cliente dueño (room `order:{id}`) le llega `PEDIDO_ESTADO`.

> Si un rol ve **tanto** el estado viejo como el nuevo, recibe solo `UPSERT`: el pedido sigue
> en su tablero, solo cambió de sección.

Ejemplos (con el mapa de visibilidad actual):

- Cliente crea pedido → `PENDIENTE`: el cajero recibe `UPSERT` (cola operable).
- `PENDIENTE → CONFIRMADO`: cajero `UPSERT` (pasa a "en cocina"), cocina `UPSERT`.
- `CONFIRMADO → EN_PREP`: cajero `UPSERT` (sigue en "en cocina"), cocina `UPSERT`.
- `EN_PREP → LISTO`: cajero `UPSERT` (vuelve a su cola operable), cocina `REMOVE`.
- `* → CANCELADO`: cajero `UPSERT` (sección cancelados); cocina `REMOVE` si venía de
  `CONFIRMADO`/`EN_PREP`. El cliente recibe `PEDIDO_ESTADO`.
- `LISTO → ENTREGADO`: cajero `UPSERT` (sección entregados); nadie más en staff.

> **Importante:** los clientes (rol no-staff) **no** se unen a ninguna room `role:` —
> solo pueden seguir pedidos propios vía `subscribe-order`.

---

## Códigos de cierre

| Código | Motivo                                                |
|--------|-------------------------------------------------------|
| `1008` | Falta token, token inválido/expirado, o usuario inactivo |
