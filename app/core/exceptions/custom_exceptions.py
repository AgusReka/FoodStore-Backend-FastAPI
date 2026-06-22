# =============================================================================
# custom_exceptions.py — Excepciones de dominio de la aplicación
# =============================================================================
#
# CONCEPTO CLAVE: ¿Por qué excepciones CUSTOM y no usar HTTPException en todos lados?
# ----------------------------------------------------
# 1. SEPARACIÓN DE CAPAS:
#    El SERVICE no debería saber de HTTP (HTTP es detalle del router).
#    Si el service lanza HTTPException, está acoplado a FastAPI.
#    Con excepciones de dominio, el service es testeable sin HTTP.
#
# 2. EXCEPCIONES ESPECÍFICAS:
#    HTTPException(404, "X") mezcla "qué pasó" con "cómo responder".
#    ResourceNotFoundError("X") describe solo "qué pasó" → el handler
#    decide el status code (404) y el formato de la respuesta.
#
# 3. JERARQUÍA:
#    Si todas heredan de AppError, podemos tener un handler que las
#    capture a todas y producir respuestas consistentes.
# =============================================================================


class AppError(Exception):
    """
    Excepción base de la aplicación.

    Todas las excepciones de dominio heredan de esta clase. Esto permite:
      - Un handler global que captura AppError → respuesta JSON estructurada.
      - Tests que verifican "se lanzó CUALQUIER error de la app" fácilmente.

    Atributos:
        message: descripción legible para humanos.
        status_code: código HTTP sugerido (puede ser sobreescrito por el handler).
        code: código de error interno (estable, no traducible). Útil para i18n.
    """

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str = "Error interno de la aplicación",
        status_code: int | None = None,
        code: str | None = None,
    ) -> None:
        # Inicializamos Exception con el mensaje (para logging, repr, etc.).
        super().__init__(message)
        self.message = message
        # Si nos pasan status_code/code, sobrescriben los defaults de la clase.
        if status_code is not None:
            self.status_code = status_code
        if code is not None:
            self.code = code


# ─── 404 Not Found ────────────────────────────────────────────────────────────

class ResourceNotFoundError(AppError):
    """
    El recurso solicitado no existe.

    Ejemplo de uso en un service:
        producto = uow.productos.get_by_id(id)
        if not producto:
            raise ResourceNotFoundError(
                resource="producto",
                identifier=id,
            )
    """

    status_code = 404
    code = "not_found"

    def __init__(
        self,
        message: str | None = None,
        resource: str | None = None,
        identifier: str | int | None = None,
    ) -> None:
        # Si no nos pasan `message` pero sí `resource`, construimos uno
        # legible: "No se encontró el producto con identificador '42'."
        if message is None and resource is not None:
            message = f"No se encontró el {resource}"
            if identifier is not None:
                message += f" con identificador '{identifier}'"
            message += "."
        if message is None:
            message = "Recurso no encontrado"
        super().__init__(message=message)
        # Guardamos resource e identifier como atributos por si el handler
        # los quiere usar en el JSON de respuesta (extra).
        self.resource = resource
        self.identifier = str(identifier) if identifier is not None else None


# ─── 409 Conflict ────────────────────────────────────────────────────────────

class DuplicateResourceError(AppError):
    """
    Se intentó crear un recurso que ya existe (violación de unicidad).

    Ejemplo: registrar un usuario con un email que ya está en la BD.
    """

    status_code = 409
    code = "duplicate_resource"

    def __init__(
        self,
        message: str | None = None,
        resource: str | None = None,
        field: str | None = None,
        value: str | int | None = None,
    ) -> None:
        if message is None and resource is not None:
            message = f"Ya existe un {resource}"
            if field is not None:
                message += f" con {field}='{value}'"
            message += "."
        if message is None:
            message = "El recurso ya existe"
        super().__init__(message=message)
        self.resource = resource
        self.field = field
        self.value = str(value) if value is not None else None


# ─── 409 Conflict (estado) ───────────────────────────────────────────────────

class ConflictError(AppError):
    """
    La operación entra en conflicto con el estado actual del recurso.

    Diferencia con DuplicateResourceError (también 409): aquí NO se trata de
    una violación de unicidad, sino de un conflicto de estado. Ejemplos:
    stock insuficiente, transición de estado inválida, un pedido que no puede
    cancelarse desde su estado actual.
    """

    status_code = 409
    code = "conflict"

    def __init__(self, message: str = "La operación entra en conflicto con el estado actual") -> None:
        super().__init__(message=message)


# ─── 400 Bad Request ─────────────────────────────────────────────────────────

class BusinessRuleError(AppError):
    """
    La operación viola una regla de negocio.

    Diferencia con ValidationError (422): aquí los datos son VÁLIDOS
    (tipos, formatos, longitudes) pero la OPERACIÓN no tiene sentido.
    Ejemplo: "no se puede cancelar un pedido ya entregado".
    """

    status_code = 400
    code = "business_rule_violation"

    def __init__(self, message: str = "La operación viola una regla de negocio") -> None:
        super().__init__(message=message)


# ─── 401 / 403 ───────────────────────────────────────────────────────────────

class AuthenticationError(AppError):
    """
    No se pudo autenticar al usuario (token inválido, ausente, expirado).
    """

    status_code = 401
    code = "authentication_error"

    def __init__(self, message: str = "No autenticado") -> None:
        super().__init__(message=message)


class AuthorizationError(AppError):
    """
    El usuario está autenticado pero no tiene permisos para la operación.
    """

    status_code = 403
    code = "authorization_error"

    def __init__(self, message: str = "Permisos insuficientes") -> None:
        super().__init__(message=message)


# ─── 429 Rate Limit ──────────────────────────────────────────────────────────

class RateLimitExceededError(AppError):
    """
    El cliente superó el límite de peticiones permitido.

    Esta excepción es lanzada por el RateLimitMiddleware (ver rate_limit/).
    El handler la convierte en 429 con headers Retry-After.
    """

    status_code = 429
    code = "rate_limit_exceeded"

    def __init__(
        self,
        message: str = "Demasiadas peticiones. Intenta de nuevo más tarde.",
        retry_after: int = 60,
    ) -> None:
        super().__init__(message=message)
        # Cuántos segundos debe esperar el cliente antes de reintentar.
        self.retry_after = retry_after
