"""Configuração da aplicação, lida do ambiente.

Toda credencial entra por variável de ambiente e é validada aqui, na
inicialização. Se faltar algo obrigatório, a aplicação falha ao subir em vez de
quebrar na primeira requisição que precisar do valor.
"""

from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Banco de dados ----
    database_url: str = Field(
        default="postgresql+psycopg2://chatia:chatia@localhost:5432/chatia",
        description="String de conexão SQLAlchemy.",
    )

    # ---- Autenticação ----
    jwt_secret_key: str = Field(
        default="dev-only-nao-use-em-producao",
        description="Segredo de assinatura do JWT. Em produção: openssl rand -hex 32.",
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60

    # ---- LLM (usado a partir da Fase 6) ----
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"

    # ---- CORS ----
    cors_origins: str = "http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        """CORS_ORIGINS chega como string separada por vírgula."""
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @field_validator("database_url")
    @classmethod
    def _require_supported_driver(cls, value: str) -> str:
        if not value.startswith("postgresql"):
            raise ValueError("DATABASE_URL deve apontar para um PostgreSQL.")
        return value


@lru_cache
def get_settings() -> Settings:
    """Settings é lido uma vez e reaproveitado — evita reler o .env a cada requisição."""
    return Settings()
