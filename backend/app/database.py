"""
Database Engine & Async Session Management
==========================================
Provides SQLAlchemy 2.0 / SQLModel async database connection management.

Key Responsibilities:
1. Normalizes database URLs (translating standard Render postgres:// to postgresql+asyncpg://).
2. Manages create_async_engine and async_sessionmaker for transactional dependency injection.
3. Provides get_session dependency for FastAPI route handlers.
4. Initializes tables and ensures metadata registration via init_db().
"""

from typing import AsyncGenerator
from sqlmodel import SQLModel
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from app.core.config import settings

def get_db_url() -> str:
    """
    Normalizes the database connection URL.
    
    Render and standard cloud providers provide PostgreSQL URLs in the format
    'postgres://' or 'postgresql://'. SQLAlchemy 2.0 async engine requires
    the explicit async dialect driver 'postgresql+asyncpg://'.
    
    Returns:
        str: Normalized connection string with appropriate async driver prefix.
    """
    url = settings.DATABASE_URL
    # Render provides postgres:// or postgresql://, normalize to postgresql+asyncpg://
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql+asyncpg://", 1)
    elif url.startswith("postgresql://") and not url.startswith("postgresql+asyncpg://"):
        url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
    return url

db_url = get_db_url()
is_sqlite = "sqlite" in db_url

# SQLite requires check_same_thread=False for multi-threaded asyncio execution
connect_args = {"check_same_thread": False} if is_sqlite else {}

# Primary SQLAlchemy 2.0 Async Engine
engine = create_async_engine(
    db_url,
    echo=False,
    future=True,
    connect_args=connect_args
)

# Async session factory producing non-expiring AsyncSession instances
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that yields an active database session.
    Automatically closes the session on handler completion.
    
    Yields:
        AsyncSession: Active database session for transactional queries.
    """
    async with async_session_factory() as session:
        try:
            yield session
        finally:
            await session.close()

async def init_db() -> None:
    """
    Ensures SQLModel metadata is registered and initial tables exist.
    Called during application startup lifespan.
    """
    # Import all models so metadata is registered
    import app.models  # noqa: F401
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
        if is_sqlite:
            from sqlalchemy import text
            try:
                await conn.execute(text("ALTER TABLE batch_payment_items ADD COLUMN intent_id TEXT;"))
            except Exception:
                pass
            try:
                await conn.execute(text("ALTER TABLE batch_payment_items ADD COLUMN note TEXT;"))
            except Exception:
                pass
