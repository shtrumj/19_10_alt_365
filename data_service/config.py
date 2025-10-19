"""
Settings for the data service.
"""
import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


class Settings:
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        "postgresql+psycopg2://postgres:postgres@postgres:5432/email_system",
    )
    DATA_SERVICE_TOKEN: str = os.getenv("DATA_SERVICE_TOKEN", "change-me-now")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
