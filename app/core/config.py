"""Application configuration module using Pydantic Settings."""

import os
from typing import Optional
from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    APP_NAME: str = "Agent Commerce Gateway"
    APP_ENV: str = "development"
    PORT: int = 8000
    HOST: str = "0.0.0.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "sqlite:///./agent_commerce.db"

    # Razorpay Test Mode
    RAZORPAY_KEY_ID: str = "rzp_test_AgentCommerceGatewayDemo"
    RAZORPAY_KEY_SECRET: str = "test_secret_gateway_demo_secret_2026"
    RAZORPAY_TEST_MODE: bool = True

    # AI / LLM configuration
    GEMINI_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GROQ_API_KEY: Optional[str] = None
    LLM_PROVIDER: str = "offline_deterministic"  # "gemini", "openai", "groq", "offline_deterministic"

    # Security
    GATEWAY_SECRET_KEY: str = "dev_secret_gateway_key_9fdb8385_3ab4_4117_aae8_de012ba321c5"
    AUDIT_GENESIS_HASH: str = "0000000000000000000000000000000000000000000000000000000000000000"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"


settings = Settings()
