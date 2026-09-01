from functools import lru_cache
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    app_name: str = "Agent Commerce Gateway"
    app_version: str = "1.0.0"
    debug: bool = True
    environment: str = "development"

    database_url: str = "sqlite+aiosqlite:///./agent_commerce.db"

    llm_api_key: str = ""
    llm_base_url: str = "https://api.openai.com/v1"
    llm_model: str = "gpt-4o-mini"
    llm_temperature: float = 0.1

    razorpay_key_id: str = ""
    razorpay_key_secret: str = ""
    razorpay_webhook_secret: str = ""

    secret_key: str = "change-me-in-production-min-32-chars-long"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30

    reservation_ttl_seconds: int = 300
    max_concurrent_reservations: int = 100

    audit_hash_algorithm: str = "sha256"

    demo_mode: bool = True
    seed_demo_data: bool = True

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()