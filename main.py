import asyncio

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.db.seed import run_seed
from app.core.websocket import manager
from contextlib import asynccontextmanager
from app.modules.category.router import router as category_router
from app.modules.ingredient.router import router as ingredient_router
from app.modules.product.router import router as product_router
from app.modules.images.router import router as images_router
from app.modules.pagos.router import router as pagos_router
from app.modules.pedidos.router import router as pedidos_router
from app.modules.direcciones.router import router as direcciones_router
from app.modules.user.router import router as user_router
from app.modules.stats.router import router as stats_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        run_seed()
        # Guardar el event loop principal para que las notificaciones WebSocket
        # disparadas desde endpoints/services síncronos puedan agendarse.
        manager.bind_loop(asyncio.get_running_loop())
    except Exception as e:
        print(f"[seed] Warning: {e}")

    yield


app = FastAPI(
    title="FoodStore API",
    description="Arquitectura Router → Service → UoW → Repository",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [
    "http://localhost:3000",  # React dev
    "http://localhost:5173",  # Cliente
    "http://localhost:5174",  # Admin
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )


# 👇 acá lo registrás
app.include_router(category_router, prefix="/api/v1/categories", tags=["Category"])
app.include_router(ingredient_router, prefix="/api/v1/ingredients", tags=["Ingredient"])
app.include_router(pagos_router, prefix="/api/v1/pagos", tags=["Formas de Pago"])
app.include_router(pedidos_router, prefix="/api/v1/pedidos", tags=["Pedidos"])
app.include_router(
    direcciones_router, prefix="/api/v1/direcciones", tags=["Direcciones"]
)
app.include_router(product_router, prefix="/api/v1/products", tags=["Product"])
app.include_router(images_router, prefix="/api/v1/images", tags=["Images"])
app.include_router(user_router, prefix="/api/v1/auth", tags=["Auth"])
app.include_router(stats_router, prefix="/api/v1/stats", tags=["Stats"])
