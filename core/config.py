"""Application configuration and environment settings."""
from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    APP_NAME: str = "Agentic SOAP Note System"
    APP_VERSION: str = "1.0.0"
    ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8001  # Different from LLM server port

    # Database
    DATABASE_URL: str = "postgresql://agent_user:supersecure123@db:5432/agentic_db"
    SQL_ECHO: bool = False

    # Redis (for task queue)
    REDIS_URL: str = "redis://redis:6379/0"

    # LLM Configuration
    LLM_ENDPOINT: str = "http://host.docker.internal:8000/infer"  # DGX endpoint
    LLM_MODEL: str = "mistral-7b"
    LLM_TIMEOUT: int = 30
    LLM_MAX_TOKENS: int = 1000
    LLM_TEMPERATURE: float = 0.3  # Lower temp for more consistent medical notes

    # EMR Configuration
    EMR_BASE_URL: Optional[str] = None
    EMR_USERNAME: Optional[str] = None
    EMR_PASSWORD: Optional[str] = None
    EMR_HEADLESS: bool = True
    EMR_TIMEOUT: int = 60000  # Playwright timeout in ms

    # Notifications
    SMTP_SERVER: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    NOTIFICATION_FROM_EMAIL: str = "noreply@agentic-soap.ai"

    # Security
    SECRET_KEY: str = "change-me-in-production"
    ENCRYPTION_KEY: Optional[str] = None

    # Audit & Logging
    LOG_LEVEL: str = "INFO"
    AUDIT_LOG_PATH: str = "/app/data/logs/audit.log"

    class Config:
        env_file = ".env"
        case_sensitive = True


# Global settings instance
settings = Settings()
