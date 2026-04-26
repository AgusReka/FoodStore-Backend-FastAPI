from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import create_db_and_tables
from contextlib import asynccontextmanager
from app.modules.category.router import router as category_router
from app.modules.ingredient.router import router as ingredient_router
from app.modules.product.router import router as product_router

app = FastAPI()


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(
    title="FoodStore API",
    description="Arquitectura Router → Service → UoW → Repository",
    version="1.0.0",
    lifespan=lifespan,
)

origins = [
    "http://localhost:3000",  # React dev
    "http://localhost:5173",  # Vite
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
app.include_router(category_router, prefix="/categories", tags=["Category"])
app.include_router(ingredient_router, prefix="/ingredients", tags=["Ingredient"])
app.include_router(product_router, prefix="/products", tags=["Product"])
