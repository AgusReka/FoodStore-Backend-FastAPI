# =============================================================================
# logging_middleware.py — Middleware de logging de requests/responses
# =============================================================================
#
# CONCEPTO CLAVE: ¿QUÉ ES UN MIDDLEWARE ASGI?
# ----------------------------------------------------
# Un middleware es una función que envuelve TODA la aplicación. Se ejecuta
# en tres fases:
#
#   1. PRE:  antes de pasar el request al endpoint.
#   2. APP:  llama al siguiente middleware o al endpoint.
#   3. POST: después de que el endpoint respondió.
#
# En Starlette/FastAPI se implementa como una clase con `__call__(...)`
# que recibe (scope, receive, send). El `call_next` invoca al siguiente
# eslabón de la cadena.
#
# ¿POR QUÉ ES IMPORTANTE LOGGEAR?
# ----------------------------------------------------
# - DEBUGGING: cuando algo falla, lo primero que un dev mira son los logs.
# - AUDITORÍA: quién hizo qué, cuándo, desde qué IP.
# - MÉTRICAS: cuántas requests por minuto, qué endpoints son populares.
# - SEGURIDAD: detectar patrones anómalos (spike de 401 = ataque).
#
# IMPLEMENTACIÓN: response.body se lee en un buffer
# ----------------------------------------------------
# Los middlewares en Starlette no pueden leer el body de la response
# directamente. Truco: sustituimos `send` por un wrapper que captura
# los chunks del body antes de pasarlos al cliente.
# =============================================================================

import time
import uuid
from typing import Awaitable, Callable

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.core.logger import get_logger

# Logger específico para este middleware.
logger = get_logger("app.middleware.logging")


class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware que registra cada request y su response correspondiente.

    Información loggeada:
      - method: GET, POST, etc.
      - path: ruta accedida (sin query string).
      - status_code: código HTTP de la response.
      - duration_ms: cuánto tardó el request completo.
      - request_id: identificador único (para correlacionar logs).
      - client_ip: IP del cliente (con cuidado si hay proxy reverso).
      - user_agent: navegador/cliente.

    NOTA: este middleware lee el body de la response para loguearlo.
    En producción, loggear bodies grandes puede ser un problema de:
      - PERFORMANCE: serializar JSON es caro.
      - SEGURIDAD: si la response tiene datos sensibles, los filtrás.
    Por eso está DESACTIVADO por defecto. Activar solo en debugging.
    """

    # Rutas a EXCLUIR del logging (suelen ser muy verbosas y poco útiles).
    EXCLUDED_PATHS: set[str] = {
        "/health",
        "/favicon.ico",
        "/openapi.json",
        "/docs",
        "/redoc",
    }

    def __init__(self, app: ASGIApp, log_body: bool = False) -> None:
        """
        Args:
            app: la siguiente capa en la cadena ASGI.
            log_body: si True, loggea el body de la response (peligroso en prod).
        """
        super().__init__(app)
        self.log_body = log_body

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        """
        Lógica del middleware: se ejecuta una vez por request.

        `call_next` es el puntero al siguiente eslabón (otro middleware o el endpoint).
        Devuelve la Response producida.
        """
        # ── FASE 1: PRE-request ──────────────────────────────────────────────
        # Generamos un ID único para correlacionar logs de un mismo request.
        request_id = str(uuid.uuid4())
        start_time = time.perf_counter()  # Más preciso que time.time().

        # Guardamos el request_id en el state para que otros middlewares
        # o el endpoint puedan accederlo (ej: incluirlo en responses).
        request.state.request_id = request_id

        # Si la ruta está excluida, dejamos pasar sin loggear.
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        # Logueamos el request entrante. Usamos %s para que el logging
        # formatee lazy (más eficiente que f-strings).
        logger.info(
            "→ %s %s [id=%s] from=%s ua=%s",
            request.method,
            request.url.path,
            request_id,
            self._get_client_ip(request),
            request.headers.get("user-agent", "unknown"),
        )

        # ── FASE 2: llamada al siguiente eslabón ─────────────────────────────
        # IMPORTANTE: cualquier excepción del endpoint se propaga hacia arriba.
        # Los exception_handlers la capturarán (ver exception_handlers.py).
        try:
            response = await call_next(request)
        except Exception as exc:
            # Si llegamos acá, NINGÚN exception handler pudo manejar la excepción
            # (caso raro). Loggeamos con nivel ERROR.
            duration_ms = (time.perf_counter() - start_time) * 1000
            logger.error(
                "✗ %s %s [id=%s] EXCEPTION after %.1fms: %s",
                request.method,
                request.url.path,
                request_id,
                duration_ms,
                repr(exc),
            )
            raise  # Relanza para que ASGI server la maneje.

        # ── FASE 3: POST-request ─────────────────────────────────────────────
        duration_ms = (time.perf_counter() - start_time) * 1000

        # Elegimos el nivel según el status code:
        #   2xx/3xx → INFO (todo bien)
        #   4xx     → WARNING (error del cliente)
        #   5xx     → ERROR (error del servidor)
        if response.status_code >= 500:
            log_level = logger.error
        elif response.status_code >= 400:
            log_level = logger.warning
        else:
            log_level = logger.info

        log_level(
            "← %s %s [id=%s] %d in %.1fms",
            request.method,
            request.url.path,
            request_id,
            response.status_code,
            duration_ms,
        )

        # Inyectamos el request_id en los headers de la response.
        # Útil para que el frontend lo incluya en tickets de soporte
        # y devs puedan buscarlo en los logs.
        response.headers["X-Request-ID"] = request_id

        return response

    @staticmethod
    def _get_client_ip(request: Request) -> str:
        """
        Extrae la IP del cliente, considerando proxies.

        En producción suele haber un load balancer / reverse proxy
        (nginx, CloudFront, etc.) que agrega el header X-Forwarded-For.
        La IP REAL del cliente está en ese header, no en request.client.

        Confiar en X-Forwarded-For es PELIGROSO si no hay un proxy de
        confianza (cualquiera puede mandar el header falsificado).
        En producción, configurar trusted_proxies en el LB.
        """
        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            # X-Forwarded-For: "client, proxy1, proxy2"
            return forwarded.split(",")[0].strip()
        return request.client.host if request.client else "unknown"
