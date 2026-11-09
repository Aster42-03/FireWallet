"""
Application Configuration & Environment Settings
================================================
Centralized configuration model using Pydantic Settings (Pydantic v2).
Loads settings from environment variables and optional .env file.
"""

import os
from pathlib import Path
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

BASE_DIR = Path(__file__).resolve().parent.parent.parent

def resolve_database_url() -> str:
    """
    Resolves DATABASE_URL. If using default SQLite, guarantees an absolute path
    pointing to the canonical project database file so execution from any directory
    (root, backend/, etc.) always accesses the same database.
    """
    raw = os.environ.get("DATABASE_URL", "")
    if raw:
        return raw
    # If SQLite file path, anchor it to project root
    db_file = BASE_DIR / "firewallet.db"
    return f"sqlite+aiosqlite:///{db_file}"

class Settings(BaseSettings):
    """
    Global application settings.
    Attributes are loaded from environment variables or .env with fallbacks.
    """
    model_config = SettingsConfigDict(
        env_file=(
            str(BASE_DIR / ".env"),
            str(BASE_DIR.parent / ".env"),
            ".env"
        ),
        extra="ignore"
    )

    PROJECT_NAME: str = "FireWallet"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Database Configuration
    DATABASE_URL: str = Field(
        default_factory=resolve_database_url,
        description="Database connection string (SQLite for local dev, PostgreSQL for production)"
    )
    
    # PayPal Developer Sandbox (REST API credentials)
    PAYPAL_ENV: str = "sandbox"
    PAYPAL_BASE_URL: str = "https://api-m.sandbox.paypal.com"
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_WEBHOOK_ID: str = ""
    PAYPAL_VAULT_RECEIVER_EMAIL: str = "vault-receiver@sandbox.paypal.com"
    PAYPAL_BILL_PAYEE_EMAIL: str = "landlord@sandbox.paypal.com"
    
    # Groq Primary LLM Service (High-Performance LLM for Monolithic CoachDecision)
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    # Secondary LLM Fallback Service (OpenAI-compatible inference endpoint)
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    
    # Networking, Public Host URL & CORS Whitelist
    APP_PUBLIC_URL: str = "http://localhost:8000"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> List[str]:
        """
        Parses comma-separated CORS_ORIGINS string into a clean list of allowed origins.
        """
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

# Singleton settings instance
settings = Settings()
