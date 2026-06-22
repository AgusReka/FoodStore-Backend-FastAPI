# Subpaquete de middlewares.
#
# Un middleware en ASGI/Starlette/FastAPI es una función que se ejecuta
# para CADA request, antes (y después) del endpoint.
#
# Estructura típica:
#
#   Request → [M1] → [M2] → [endpoint] → [M2'] → [M1'] → Response
#
# El orden importa: el primer middleware agregado con app.add_middleware()
# es el más EXTERNO (se ejecuta primero al recibir, último al responder).
