from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings, loaded from environment variables or backend/.env.

    SECRET_KEY and DATABASE_URL have no defaults on purpose: the application
    must never start with a guessed secret or a guessed database password.
    """

    APP_NAME: str = "AgentDB"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    # JWT configuration
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database (MySQL 8.0+ via PyMySQL)
    DATABASE_URL: str

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )


settings = Settings()
