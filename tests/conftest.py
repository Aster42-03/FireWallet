import asyncio
import os
from typing import AsyncGenerator
from uuid import uuid4
from datetime import datetime, timezone, timedelta, date

import pytest
import pytest_asyncio
import httpx
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.database import get_session
from app.models.user import User, BudgetPolicy
from app.models.bucket import Bucket
from app.models.ledger import LedgerEntry
from app.models.bill import Bill

def is_docker_available() -> bool:
    """Check if local Docker daemon is reachable for Testcontainers."""
    try:
        import docker
        client = docker.from_env()
        return bool(client.ping())
    except Exception:
        return False

@pytest_asyncio.fixture(scope="function")
async def test_engine():
    """Create an isolated, in-memory SQLite async engine for fast unit tests."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        echo=False
    )
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    yield engine

    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.drop_all)
    await engine.dispose()

@pytest_asyncio.fixture(scope="function")
async def session(test_engine) -> AsyncGenerator[AsyncSession, None]:
    """Provide a fresh, isolated SQLModel AsyncSession for each test."""
    session_factory = async_sessionmaker(
        bind=test_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False
    )
    async with session_factory() as sess:
        yield sess

@pytest_asyncio.fixture(scope="function")
async def seeded_session(session: AsyncSession) -> AsyncSession:
    """Pre-populate session with demo user Aster and 5 Trinity buckets with positive balances."""
    # 1. Create User
    user = User(
        email="test-aster@sandbox.paypal.com",
        display_name="Aster (Test Runner)",
        timezone="America/New_York"
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)

    # 2. Create Budget Policy
    policy = BudgetPolicy(
        user_id=user.id,
        currency="USD",
        vault_skim_bps=2000,           # 20.00%
        daily_amount=4000,             # $40.00
        freedom_monthly_amount=15000,  # $150.00
        bank_spend_requires_override=True,
        vault_spend_allowed=False,
        override_min_chars=200,
        override_cooldown_seconds=180
    )
    session.add(policy)

    # 3. Create 5 Trinity Buckets
    bucket_kinds = [
        ("bank", "Bank Foundation"),
        ("daily", "Daily Allowance"),
        ("freedom", "Freedom Envelope"),
        ("vault", "Locked Savings Vault"),
        ("bills", "Reserved Bills")
    ]
    buckets = {}
    for kind, name in bucket_kinds:
        b = Bucket(user_id=user.id, kind=kind, name=name)
        session.add(b)
        await session.commit()
        await session.refresh(b)
        buckets[kind] = b

    # 4. Seed Positive Double-Entry Ledger Balances
    initial_balances = [
        (buckets["bank"], 80000, "Bank Baseline"),       # $800.00
        (buckets["daily"], 5200, "Daily + Rollover"),     # $52.00
        (buckets["freedom"], 9000, "Freedom Fun Money"),  # $90.00
        (buckets["vault"], 20000, "Locked Vault"),       # $200.00
        (buckets["bills"], 120000, "Rent Reserve")       # $1,200.00
    ]
    for b, amt, note in initial_balances:
        entry = LedgerEntry(
            transfer_id=uuid4(),
            user_id=user.id,
            bucket_id=b.id,
            amount=amt,
            currency="USD",
            state="posted",
            idempotency_key=f"seed:{b.kind}:{uuid4()}",
            created_at=datetime.now(timezone.utc),
            posted_at=datetime.now(timezone.utc)
        )
        session.add(entry)

    # 5. Scheduled Bill
    rent_bill = Bill(
        user_id=user.id,
        name="Apartment Rent",
        amount=120000,
        due_date=date.today() + timedelta(days=5),
        payee_email="landlord@sandbox.paypal.com",
        priority=1,
        status="scheduled"
    )
    session.add(rent_bill)
    await session.commit()

    return session

@pytest_asyncio.fixture(scope="function")
async def client(seeded_session: AsyncSession) -> AsyncGenerator[httpx.AsyncClient, None]:
    """FastAPI TestClient with injected dependency override for seeded database session."""
    async def override_get_session():
        yield seeded_session

    app.dependency_overrides[get_session] = override_get_session
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
