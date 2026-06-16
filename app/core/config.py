# app/core/config.py
from pydantic import computed_field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """
    Configuración cargada desde variables de entorno o archivo .env.

    Acepta las variables individuales de Postgres y construye DATABASE_URL
    automáticamente con @computed_field, o usa DATABASE_URL directamente
    si se provee en el entorno.

    Orden de prioridad (pydantic-settings):
      1. Variables de entorno del sistema
      2. Archivo .env
      3. Defaults declarados en la clase
    """

    postgres_user: str = "postgres"
    postgres_password: str = "password"
    postgres_db: str = "team_hero_db"
    postgres_host: str = "localhost"
    postgres_port: int = 5433

    @computed_field
    @property
    def DATABASE_URL(self) -> str:
        return (
            f"postgresql://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )

    # ─── JWT ──────────────────────────────────────────────────────────────────
    SECRET_KEY: str                    # Obligatorio — sin default. Mínimo 32 chars.
    ALGORITHM:  str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30

    # ─── Cloudinary ───────────────────────────────────────────────────────────
    cloudinary_cloud_name: str
    cloudinary_api_key: str
    cloudinary_api_secret: str

    # ─── MercadoPago ─────────────────────────────────────────────────────────
    MP_ACCESS_TOKEN: str = ""
    MP_PUBLIC_KEY: str = ""
    MP_WEBHOOK_URL: str = ""
    NGROK_URL: str = ""
    VITE_FRONTEND_URL: str = "http://localhost:5173"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
