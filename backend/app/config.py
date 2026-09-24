"""Application configuration via environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """LanQuiz runtime settings."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "LanQuiz"
    host: str = "0.0.0.0"
    port: int = 8000
    host_ip: str = "localhost"
    data_dir: Path = Path("./data")
    log_level: str = "INFO"
    cors_origins: str = "*"
    score_base: int = 1000
    jwt_secret: str = "change-me-lanquiz-dev-secret"
    jwt_expire_hours: int = 72

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.data_dir / 'lanquiz.db'}"

    @property
    def public_base_url(self) -> str:
        return f"http://{self.host_ip}:{self.port}"

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
