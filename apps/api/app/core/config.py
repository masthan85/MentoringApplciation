"""Application settings, loaded once from the environment."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

Environment = Literal["local", "test", "staging", "production"]
AuthMode = Literal["oidc", "dev"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    env: Environment = "local"
    log_level: str = "INFO"
    service_name: str = "mentor-api"
    cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])

    # Runtime connection (non-superuser role, row-level security applies).
    database_url: str = "postgresql+asyncpg://mentor_app:mentor_app@localhost:5432/mentor"
    # Used only by Alembic. Owns the schema.
    migration_database_url: str = "postgresql+asyncpg://mentor:mentor@localhost:5432/mentor"
    redis_url: str = "redis://localhost:6379/0"

    # Auth. "oidc" verifies RS256/ES256 tokens against the provider's JWKS.
    # "dev" accepts HS256 tokens signed with dev_auth_secret and is refused
    # outside local and test environments.
    auth_mode: AuthMode = "oidc"
    auth_issuer: str | None = None
    auth_audience: str | None = None
    auth_jwks_url: str | None = None
    auth_algorithms: list[str] = Field(default_factory=lambda: ["RS256"])
    auth_admin_claim: str = "roles"
    auth_admin_role: str = "admin"
    # Development sign-in only: these emails get the admin role from /v1/dev/login.
    dev_admin_emails: list[str] = Field(default_factory=list)
    dev_auth_secret: SecretStr = SecretStr("dev-only-secret-change-me-0123456789abcdef")

    # LLM gateway. Keys come from the environment only.
    anthropic_api_key: SecretStr | None = None
    openai_api_key: SecretStr | None = None
    llm_routes_file: str | None = None
    llm_default_provider: Literal["anthropic", "openai", "mock"] = "anthropic"
    llm_cost_warn_usd_per_turn: float = 0.25

    # Mentor packs (YAML). Defaults to the repository's /packs directory.
    packs_dir: str | None = None
    lens_switch_threshold: float = 0.7

    # Second-stage reranking for retrieval. "cross_encoder" needs `uv sync --group rerank`.
    reranker: Literal["heuristic", "cross_encoder"] = "heuristic"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # Background jobs: "arq" enqueues to the worker, "inline" runs in-process
    # (local development without a worker, and tests).
    jobs_mode: Literal["arq", "inline"] = "arq"

    # Key for encrypting sensitive memories (urlsafe base64, 32 bytes).
    # Required in staging and production; a fixed development key is used otherwise.
    sensitive_data_key: SecretStr | None = None

    # Observability
    otel_exporter_otlp_endpoint: str | None = None

    # Rate limiting (requests per minute)
    rate_limit_per_user: int = 120
    rate_limit_per_ip: int = 300

    @model_validator(mode="after")
    def _check_auth(self) -> "Settings":
        if self.auth_mode == "dev" and self.env not in ("local", "test"):
            raise ValueError("AUTH_MODE=dev is only allowed when ENV is local or test")
        if self.auth_mode == "oidc" and self.env != "test":
            missing = [
                name
                for name in ("auth_issuer", "auth_audience", "auth_jwks_url")
                if not getattr(self, name)
            ]
            if missing:
                raise ValueError(
                    f"AUTH_MODE=oidc needs {', '.join(m.upper() for m in missing)} to be set"
                )
        if self.env in ("staging", "production"):
            # The dev secret has no use here, so never keep one in memory.
            self.dev_auth_secret = SecretStr("")
            if not self.sensitive_data_key:
                raise ValueError("SENSITIVE_DATA_KEY must be set in staging and production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
