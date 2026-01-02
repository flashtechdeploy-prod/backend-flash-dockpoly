import os
from typing import List
from urllib.parse import urlparse, urlunparse
from pydantic_settings import BaseSettings, SettingsConfigDict

# Get the project root directory (flash-full folder)
_PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
_DEFAULT_SQLITE_PATH = os.path.join(_PROJECT_ROOT, "flash_erp.db")


class Settings(BaseSettings):
    """Application settings."""

    model_config = SettingsConfigDict(
        env_file=(
            "backend/backend.env",
            "backend.env",
            "backend/.env",
            ".env",
        ),
        case_sensitive=True,
    )
    
    # Application
    APP_NAME: str = "Flash ERP"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    
    # Database - Default to SQLite for local development
    DATABASE_URL: str = f"sqlite:///{_DEFAULT_SQLITE_PATH}"

    # Uploads
    UPLOADS_DIR: str = os.path.join(_PROJECT_ROOT, "uploads")
    
    # Security
    SECRET_KEY: str = "your-super-secret-key-change-this-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://localhost:3001"
    
    @property
    def allowed_origins_list(self) -> List[str]:
        """Convert comma-separated string to list."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]
    
settings = Settings()


def _redact_database_url(database_url: str) -> str:
    try:
        parsed = urlparse(database_url)
        if parsed.scheme.startswith("sqlite"):
            return database_url

        if parsed.username:
            host = parsed.hostname or ""
            port = f":{parsed.port}" if parsed.port else ""
            netloc = f"{parsed.username}:***@{host}{port}"
            return urlunparse(parsed._replace(netloc=netloc))

        return database_url
    except Exception:
        return "<redacted>"


def _normalize_database_url(database_url: str) -> str:
    if database_url.startswith("postgres://"):
        return "postgresql+psycopg://" + database_url[len("postgres://"):]
    if database_url.startswith("postgresql://"):
        return "postgresql+psycopg://" + database_url[len("postgresql://"):]
    return database_url

# Log the database being used
settings.DATABASE_URL = _normalize_database_url(settings.DATABASE_URL)
print(f"[Config] Using database: {_redact_database_url(settings.DATABASE_URL)}")
