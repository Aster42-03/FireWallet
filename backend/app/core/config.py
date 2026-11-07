import os
from typing import List
from pydantic_settings import BaseSettings
from pydantic import Field

class Settings(BaseSettings):
    PROJECT_NAME: str = "FireWallet"
    VERSION: str = "0.1.0"
    API_V1_STR: str = "/api/v1"
    
    # Database
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///./firewallet.db",
        description="Database connection string (SQLite for local dev, PostgreSQL for production)"
    )
    
    # PayPal Sandbox
    PAYPAL_ENV: str = "sandbox"
    PAYPAL_BASE_URL: str = "https://api-m.sandbox.paypal.com"
    PAYPAL_CLIENT_ID: str = ""
    PAYPAL_CLIENT_SECRET: str = ""
    PAYPAL_WEBHOOK_ID: str = ""
    PAYPAL_VAULT_RECEIVER_EMAIL: str = "vault-receiver@sandbox.paypal.com"
    PAYPAL_BILL_PAYEE_EMAIL: str = "landlord@sandbox.paypal.com"
    
    # LLM Service (OpenAI-compatible)
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-4o-mini"
    
    # Public URL & CORS
    APP_PUBLIC_URL: str = "http://localhost:8000"
    CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origin_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
