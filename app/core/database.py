from sqlmodel import SQLModel, Session, create_engine
from app.core.config import settings

engine = create_engine(settings.DATABASE_URL, echo=False)


def create_db_and_tables() -> None:
    """Crea todas las tablas definidas con SQLModel al iniciar la app."""
    SQLModel.metadata.create_all(engine)


def get_session():
    """
    Dependencia FastAPI que provee una Session por request.
    Usada exclusivamente por el UnitOfWork — no inyectar directo en routers.
    """
    with Session(engine) as session:
        yield session
