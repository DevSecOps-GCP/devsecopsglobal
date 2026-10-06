from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration. Secrets come from env vars rendered by Vault Secrets Operator."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "DevSecOps Global"
    log_level: str = "INFO"
    enable_docs: bool = True

    db_host: str = "localhost"
    db_port: int = 5432
    db_name: str = "learnhub"
    db_user: str = "learnhub"
    db_password: SecretStr = SecretStr("learnhub")
    db_ssl: Literal["disable", "require", "verify-ca"] = "disable"
    db_ca_cert: str | None = None
    db_pool_size: int = 5

    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: SecretStr | None = None
    redis_tls: bool = False
    redis_ca_cert: str | None = None
    redis_timeout_seconds: float = 0.5

    jwt_secret: SecretStr = SecretStr("local-dev-only-change-me-0123456789abcdef")
    jwt_ttl_minutes: int = 60
    cookie_name: str = "dsg_session"
    cookie_secure: bool = True
    # How many proxies append to X-Forwarded-For. GCLB appends "<client>,<lb>" -> 2.
    # 0 = trust only the socket peer.
    trusted_xff_hops: int = 0
    login_attempts_per_minute: int = 5
    signups_per_hour_per_ip: int = 10

    storage_backend: Literal["local", "gcs"] = "local"
    local_storage_dir: str = "/data/media"
    gcs_bucket: str | None = None
    download_url_ttl_seconds: int = 7200
    upload_url_ttl_seconds: int = 1800
    max_upload_bytes: int = 2 * 1024**3
    allowed_video_types: list[str] = Field(
        default=["video/mp4", "video/webm", "video/quicktime", "video/ogg"]
    )

    catalog_cache_ttl_seconds: int = 60

    # First admin, created once by `python -m app.cli bootstrap-admin` in the migration job
    admin_email: str | None = None
    admin_password: SecretStr | None = None
    admin_full_name: str = "Admin"


@lru_cache
def get_settings() -> Settings:
    return Settings()
