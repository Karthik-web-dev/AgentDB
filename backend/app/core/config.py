from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy.engine import URL


class Settings(BaseSettings):
    """Application settings, loaded from environment variables or backend/.env.

    SECRET_KEY is required. MySQL credentials may be supplied as a URL or discrete DB_*
    values, so URL-reserved password characters are encoded safely.
    """

    APP_NAME: str = "AgentDB"
    DEBUG: bool = False
    API_V1_STR: str = "/api/v1"

    # JWT configuration
    SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database (MySQL 8.0+ via PyMySQL)
    DATABASE_URL: str | None = None
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_NAME: str = "agentdb"
    DB_USER: str = "root"
    DB_PASSWORD: str = ""

    # OpenAI-compatible chat completions API (OpenRouter by default).
    OPENROUTER_BASE_URL: str = "https://openrouter.ai/api/v1"
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_SITE_URL: str = "http://localhost:8080"
    OPENROUTER_APP_NAME: str = "AgentDB"
    AGENT_MEMORY_MESSAGES: int = 20
    AGENT_MEMORY_RECENT_MAX_CHARS: int = 24000
    AGENT_MEMORY_SUMMARY_MAX_CHARS: int = 5000
    AGENT_MEMORY_SUMMARIZE_CHUNK_CHARS: int = 5000
    LLM_MAX_OUTPUT_TOKENS: int = 2048
    LLM_TIMEOUT_SECONDS: int = 90

    # CORS
    BACKEND_CORS_ORIGINS: List[str] = ["http://localhost:3000", "http://localhost:5173"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    @property
    def sqlalchemy_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        if not self.DB_PASSWORD:
            raise ValueError("Set DATABASE_URL or DB_PASSWORD for MySQL connectivity.")
        return URL.create(
            "mysql+pymysql", username=self.DB_USER, password=self.DB_PASSWORD,
            host=self.DB_HOST, port=self.DB_PORT, database=self.DB_NAME,
        ).render_as_string(hide_password=False)

settings = Settings()
