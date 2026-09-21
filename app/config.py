"""Application configuration loaded exclusively from environment variables."""

from functools import lru_cache

from pydantic import Field, PostgresDsn
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings. Values come from the process environment or a local `.env` file."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_name: str = "autonomous-job-search-agent"
    app_env: str = "development"
    debug: bool = False
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    database_url: PostgresDsn = Field(
        default=PostgresDsn("postgresql+psycopg://jobsearch:jobsearch@localhost:5433/jobsearch")
    )
    database_pool_size: int = Field(default=5, ge=1)
    database_max_overflow: int = Field(default=10, ge=0)
    openai_api_key: str | None = None
    openai_model: str = "gpt-4o-mini"
    openai_evaluation_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    openai_evaluation_seed: int = Field(default=42, ge=0)
    openai_input_usd_per_million: float = Field(default=0.15, ge=0.0)
    openai_output_usd_per_million: float = Field(default=0.60, ge=0.0)
    evaluation_batch_limit_default: int = Field(default=50, ge=1)
    evaluation_batch_limit_max: int = Field(default=200, ge=1)
    evaluation_concurrency: int = Field(default=2, ge=1, le=16)
    evaluation_concurrency_max: int = Field(default=8, ge=1, le=16)
    evaluation_rate_limit_per_minute: int = Field(default=30, ge=0)

    @property
    def sqlalchemy_database_uri(self) -> str:
        return str(self.database_url)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
