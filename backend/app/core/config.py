from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "SmartOpsDocs"
    database_url: str = "sqlite:///./data/smartopsdocs.db"
    jwt_secret: str = Field(default="change-me-for-local-dev")
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24
    initial_admin_username: str = "admin"
    initial_admin_password: str = "admin123"
    cors_origins: str = "http://127.0.0.1:5173,http://localhost:5173"
    upload_dir: Path = Path("./data/uploads")
    knowledge_dir: Path = Path("./data/knowledge")
    max_upload_size_mb: int = 50
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_vision_model: str | None = None
    docx_vision_max_images: int = 20
    agent_runtime: str = "local-openclaw"
    openclaw_endpoint: str | None = None
    openclaw_api_key: str | None = None
    openclaw_agent: str = "smartopsdocs-ops-agent"


@lru_cache
def get_settings() -> Settings:
    return Settings()
