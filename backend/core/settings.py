from __future__ import annotations

from pathlib import Path

from pydantic import Field, field_validator
from pydantic_core import PydanticCustomError
from pydantic_settings import BaseSettings, SettingsConfigDict

from backend.core.__version__ import __version__
from backend.enums import LogLevel


class Settings(BaseSettings):
    """Bootstrap settings loaded from environment variables."""

    # application data directory
    data_dir: Path = Field(
        default=Path("./data"), description="Directory for database, logs, cache"
    )

    # static directory
    static_dir: Path = Field(
        default=Path("./data/static"), description="Directory for static files"
    )

    # avatars directory
    avatars_dir: Path = Field(
        default=Path("./data/static/avatars"), description="Directory for user avatars"
    )

    # logging
    log_level: str = Field(
        default="INFO", description="Log level: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )

    # admin
    admin_password: str | None = Field(
        default=None, description="Initial admin password"
    )

    # API configuration
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    cors_origins: str = "*"  # comma-separated list or "*" for all

    # JWT authentication
    jwt_secret: str | None = Field(
        default=None, description="Secret key for JWT tokens"
    )
    jwt_algorithm: str = "HS256"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("log_level")
    @classmethod
    def validate_log_level(cls, v: str) -> str:
        """Validate log level is valid."""
        try:
            return str(LogLevel(v.upper())).upper()
        except ValueError:
            return "INFO"

    @field_validator("jwt_secret", mode="before")
    @classmethod
    def validate_jwt_secret(cls, v: str | None) -> str | None:
        """Validate JWT secret is set and not empty."""
        if isinstance(v, str):
            v = v.strip()
        if not v:
            raise PydanticCustomError("jwt_secret", "JWT secret must be set")
        return v

    @property
    def data_dir_path(self) -> Path:
        """Get data directory as Path object (ensures directory exists)."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir

    @property
    def static_dir_path(self) -> Path:
        """Get static directory as Path object (ensures directory/sub directories exists)."""
        self.static_dir.mkdir(parents=True, exist_ok=True)
        return self.static_dir

    @property
    def avatars_dir_path(self) -> Path:
        """Get avatars directory as Path object (ensures directory exists)."""
        self.avatars_dir.mkdir(parents=True, exist_ok=True)
        return self.avatars_dir

    @property
    def db_path(self) -> Path:
        """Get database file path."""
        db_path = self.data_dir_path / "database" / "reclaimerr.db"
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return db_path

    @property
    def log_level_enum(self) -> LogLevel:
        """Get log level as enum."""
        try:
            return LogLevel[self.log_level]
        except KeyError:
            return LogLevel.INFO

    @property
    def log_dir(self) -> Path:
        """Get log directory path."""
        log_path = self.data_dir_path / "logs"
        log_path.mkdir(parents=True, exist_ok=True)
        return log_path

    @property
    def cors_origins_list(self) -> list[str]:
        """Convert comma-separated CORS origins to list."""
        if not self.cors_origins or self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def version(self) -> str:
        """Get application version."""
        return str(__version__)


# global settings instance
settings = Settings()
