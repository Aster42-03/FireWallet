"""
FireWallet Main Application Entrypoint
======================================
FastAPI application configuring routes, CORS middleware, lifespan database startup,
and system health check endpoints.

Architecture:
- API v1 routers registered under settings.API_V1_STR (/api/v1).
- Lifespan context initializes SQLModel metadata and database tables.
- Dual-support for SQLite (local dev) and PostgreSQL/asyncpg (Render production).
"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.database import init_db
from app.api.v1.auth import router as auth_router
from app.api.v1.buckets import router as buckets_router
from app.api.v1.intents import router as intents_router
from app.api.v1.overrides import router as overrides_router
from app.api.v1.bills import router as bills_router
from app.api.v1.stats import router as stats_router
from app.api.v1.analytics import router as analytics_router
from app.api.v1.coach import router as coach_router
from app.api.v1.webhooks import router as webhooks_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Executes startup routines (database verification, table registration)
    before incoming requests are processed.
    """
    # Startup: ensure tables exist in SQLite or Postgres
    await init_db()
    yield

# Initialize FastAPI application with OpenAPI metadata
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="Proactive Financial Firewall & AI Coach powered by the Trinity Bucket Engine",
    lifespan=lifespan
)

# Cross-Origin Resource Sharing (CORS) Configuration
# Permits localhost frontend clients during local dev and production Render URLs
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list + ["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API v1 modular feature routers
prefix = settings.API_V1_STR
app.include_router(auth_router, prefix=prefix)
app.include_router(buckets_router, prefix=prefix)
app.include_router(intents_router, prefix=prefix)
app.include_router(overrides_router, prefix=prefix)
app.include_router(bills_router, prefix=prefix)
app.include_router(stats_router, prefix=prefix)
app.include_router(analytics_router, prefix=prefix)
app.include_router(coach_router, prefix=prefix)
app.include_router(webhooks_router, prefix=prefix)

@app.get("/health", tags=["System"])
async def health_check():
    """
    System Health Check Endpoint.
    Returns service health status, version, and active PayPal environment.
    Used by Render health monitors and container orchestration.
    """
    return {
        "status": "healthy",
        "service": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "paypal_env": settings.PAYPAL_ENV
    }

@app.get("/", tags=["System"])
async def root():
    """
    Root Welcome Endpoint.
    Directs developers to interactive Swagger UI (/docs) and health check.
    """
    return {
        "message": "Welcome to FireWallet API",
        "docs_url": "/docs",
        "health": "/health"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
