"""Application configuration via environment variables."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_JWT_SECRET = "change-me-lanquiz-dev-secret"


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
    jwt_secret: str = DEFAULT_JWT_SECRET
    jwt_expire_hours: int = 72
    allow_default_secret: bool = False

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.data_dir / 'lanquiz.db'}"

    @property
    def sync_database_url(self) -> str:
        return f"sqlite:///{self.data_dir / 'lanquiz.db'}"

    @property
    def public_base_url(self) -> str:
        return f"http://{self.host_ip}:{self.port}"

    @property
    def is_default_secret(self) -> bool:
        return self.jwt_secret == DEFAULT_JWT_SECRET

    @property
    def host_ip_is_loopback(self) -> bool:
        return self.host_ip.strip().lower() in ("localhost", "127.0.0.1", "::1")

    def ensure_secure(self) -> None:
        """Fail fast on insecure defaults. Called at startup (lifespan)."""
        if self.is_default_secret and not self.allow_default_secret:
            raise RuntimeError(
                "Insecure JWT_SECRET: set a strong JWT_SECRET env var "
                "(or ALLOW_DEFAULT_SECRET=true for local dev only)."
            )

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


settings = Settings()
