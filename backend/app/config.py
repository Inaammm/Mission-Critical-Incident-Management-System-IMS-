from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    postgres_url: str = "postgresql+asyncpg://ims:ims_secret@localhost:5432/ims_db"
    mongodb_url: str = "mongodb://localhost:27017"
    redis_url: str = "redis://localhost:6379"

    # App
    app_name: str = "Incident Management System"
    debug: bool = False

    # Rate Limiting
    rate_limit_signals_per_second: int = 10000
    rate_limit_burst: int = 15000

    # Debouncing
    debounce_window_seconds: int = 10
    debounce_threshold: int = 100

    # SLA (minutes)
    sla_p0_minutes: int = 15
    sla_p1_minutes: int = 60
    sla_p2_minutes: int = 240

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
