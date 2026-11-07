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
from app.models.intent import Intent

def is_docker_available() -> bool:
    """Check if local Docker daemon is reachable for Testcontainers."""
    if not os.path.exists("/var/run/docker.sock") and not os.environ.get("DOCKER_HOST"):
        return False
    client = None
    try:
        import docker
        client = docker.from_env()
        return bool(client.ping())
    except Exception:
        return False
    finally:
        if client:
            try:
                client.close()
            except Exception:
                pass

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

    # 4. Seed Bank-Kept Double-Entry Ledger Balances
    now = datetime.now(timezone.utc)
    
    # Inflow to Bank
    payday_transfer_id = uuid4()
    session.add(LedgerEntry(
        transfer_id=payday_transfer_id,
        user_id=user.id,
        bucket_id=buckets["bank"].id,
        amount=247000,
        currency="USD",
        state="posted",
        entry_kind="payday_inflow",
        counterparty_bucket="external_payroll",
        memo="Bi-Weekly Payroll Direct Deposit",
        idempotency_key=f"test:seed:payday:{uuid4()}",
        created_at=now - timedelta(days=5),
        posted_at=now - timedelta(days=5)
    ))

    # Bank -> Vault (20% Skim: $200.00)
    t_vault = uuid4()
    session.add(LedgerEntry(
        transfer_id=t_vault,
        user_id=user.id,
        bucket_id=buckets["bank"].id,
        amount=-20000,
        currency="USD",
        state="posted",
        entry_kind="vault_skim",
        counterparty_bucket="vault",
        memo="Payday 20% Automated Savings Skim",
        idempotency_key=f"test:seed:vault:debit:{uuid4()}",
        created_at=now - timedelta(days=5),
        posted_at=now - timedelta(days=5)
    ))
    session.add(LedgerEntry(
        transfer_id=t_vault,
        user_id=user.id,
        bucket_id=buckets["vault"].id,
        amount=20000,
        currency="USD",
        state="posted",
        entry_kind="vault_skim",
        counterparty_bucket="bank",
        memo="Payday 20% Automated Savings Skim",
        idempotency_key=f"test:seed:vault:credit:{uuid4()}",
        created_at=now - timedelta(days=5),
        posted_at=now - timedelta(days=5)
    ))

    # Bank -> Bills (Rent: $1,200.00)
    t_bills = uuid4()
    session.add(LedgerEntry(
        transfer_id=t_bills,
        user_id=user.id,
        bucket_id=buckets["bank"].id,
        amount=-120000,
        currency="USD",
        state="posted",
        entry_kind="bill_reserve",
        counterparty_bucket="bills",
        memo="November Apartment Rent Earmark",
        idempotency_key=f"test:seed:bills:debit:{uuid4()}",
        created_at=now - timedelta(days=5),
        posted_at=now - timedelta(days=5)
    ))
    session.add(LedgerEntry(
        transfer_id=t_bills,
        user_id=user.id,
        bucket_id=buckets["bills"].id,
        amount=120000,
        currency="USD",
        state="posted",
        entry_kind="bill_reserve",
        counterparty_bucket="bank",
        memo="November Apartment Rent Earmark",
        idempotency_key=f"test:seed:bills:credit:{uuid4()}",
        created_at=now - timedelta(days=5),
        posted_at=now - timedelta(days=5)
    ))

    # Bank -> Freedom ($150.00)
    t_free = uuid4()
    session.add(LedgerEntry(
        transfer_id=t_free,
        user_id=user.id,
        bucket_id=buckets["bank"].id,
        amount=-15000,
        currency="USD",
        state="posted",
        entry_kind="freedom_allocation",
        counterparty_bucket="freedom",
        memo="Monthly Freedom Envelope Credit",
        idempotency_key=f"test:seed:free:debit:{uuid4()}",
        created_at=now - timedelta(days=4),
        posted_at=now - timedelta(days=4)
    ))
    session.add(LedgerEntry(
        transfer_id=t_free,
        user_id=user.id,
        bucket_id=buckets["freedom"].id,
        amount=15000,
        currency="USD",
        state="posted",
        entry_kind="freedom_allocation",
        counterparty_bucket="bank",
        memo="Monthly Freedom Envelope Credit",
        idempotency_key=f"test:seed:free:credit:{uuid4()}",
        created_at=now - timedelta(days=4),
        posted_at=now - timedelta(days=4)
    ))

    # Bank -> Daily ($120.00)
    t_daily = uuid4()
    session.add(LedgerEntry(
        transfer_id=t_daily,
        user_id=user.id,
        bucket_id=buckets["bank"].id,
        amount=-12000,
        currency="USD",
        state="posted",
        entry_kind="morning_topup",
        counterparty_bucket="daily",
        memo="Daily Allowance Target Top-Up with Rollover",
        idempotency_key=f"test:seed:daily:debit:{uuid4()}",
        created_at=now - timedelta(days=3),
        posted_at=now - timedelta(days=3)
    ))
    session.add(LedgerEntry(
        transfer_id=t_daily,
        user_id=user.id,
        bucket_id=buckets["daily"].id,
        amount=12000,
        currency="USD",
        state="posted",
        entry_kind="morning_topup",
        counterparty_bucket="bank",
        memo="Daily Allowance Target Top-Up with Rollover",
        idempotency_key=f"test:seed:daily:credit:{uuid4()}",
        created_at=now - timedelta(days=3),
        posted_at=now - timedelta(days=3)
    ))

    # Settled Spend from Daily: Groceries -$44.00
    intent_g = Intent(
        user_id=user.id,
        utterance="Weekly groceries at Trader Joe's",
        short_tag="groceries",
        amount=4400,
        currency="USD",
        merchant_name="Trader Joe's",
        category="groceries",
        necessity="daily_living",
        recommended_bucket="daily",
        source_bucket_id=buckets["daily"].id,
        status="settled",
        paypal_order_id="5O190127TN984224L"
    )
    session.add(intent_g)
    await session.commit()
    await session.refresh(intent_g)

    session.add(LedgerEntry(
        transfer_id=uuid4(),
        user_id=user.id,
        bucket_id=buckets["daily"].id,
        amount=-4400,
        currency="USD",
        state="posted",
        entry_kind="merchant_spend",
        counterparty_bucket="paypal_merchant",
        memo="Trader Joe's groceries",
        intent_id=intent_g.id,
        paypal_order_id="5O190127TN984224L",
        paypal_capture_id="CAPTURE-TJ-998811",
        idempotency_key=f"test:seed:spend:daily:1:{uuid4()}",
        created_at=now - timedelta(days=2),
        posted_at=now - timedelta(days=2)
    ))

    # Settled Spend from Daily: Transit -$24.00
    intent_t = Intent(
        user_id=user.id,
        utterance="Subway weekly pass recharge",
        short_tag="subway transit pass",
        amount=2400,
        currency="USD",
        merchant_name="MTA Transit",
        category="transit",
        necessity="daily_living",
        recommended_bucket="daily",
        source_bucket_id=buckets["daily"].id,
        status="settled",
        paypal_order_id="3K281920PQ447192M"
    )
    session.add(intent_t)
    await session.commit()
    await session.refresh(intent_t)

    session.add(LedgerEntry(
        transfer_id=uuid4(),
        user_id=user.id,
        bucket_id=buckets["daily"].id,
        amount=-2400,
        currency="USD",
        state="posted",
        entry_kind="merchant_spend",
        counterparty_bucket="paypal_merchant",
        memo="MTA Subway recharge",
        intent_id=intent_t.id,
        paypal_order_id="3K281920PQ447192M",
        paypal_capture_id="CAPTURE-MTA-332211",
        idempotency_key=f"test:seed:spend:daily:2:{uuid4()}",
        created_at=now - timedelta(days=1),
        posted_at=now - timedelta(days=1)
    ))

    # Settled Spend from Freedom: Dining -$38.00
    intent_d = Intent(
        user_id=user.id,
        utterance="Dinner and drinks at Toki Ramen",
        short_tag="ramen dinner",
        amount=3800,
        currency="USD",
        merchant_name="Toki Ramen",
        category="eating_out",
        necessity="freedom",
        recommended_bucket="freedom",
        source_bucket_id=buckets["freedom"].id,
        status="settled",
        paypal_order_id="7B992819XX112233R"
    )
    session.add(intent_d)
    await session.commit()
    await session.refresh(intent_d)

    session.add(LedgerEntry(
        transfer_id=uuid4(),
        user_id=user.id,
        bucket_id=buckets["freedom"].id,
        amount=-3800,
        currency="USD",
        state="posted",
        entry_kind="merchant_spend",
        counterparty_bucket="paypal_merchant",
        memo="Dinner at Toki Ramen",
        intent_id=intent_d.id,
        paypal_order_id="7B992819XX112233R",
        paypal_capture_id="CAPTURE-TOKI-774411",
        idempotency_key=f"test:seed:spend:free:1:{uuid4()}",
        created_at=now - timedelta(days=2),
        posted_at=now - timedelta(days=2)
    ))

    # Settled Spend from Freedom: Concert -$22.00
    intent_c = Intent(
        user_id=user.id,
        utterance="Indie band concert ticket",
        short_tag="concert ticket",
        amount=2200,
        currency="USD",
        merchant_name="Ticketmaster",
        category="entertainment",
        necessity="freedom",
        recommended_bucket="freedom",
        source_bucket_id=buckets["freedom"].id,
        status="settled",
        paypal_order_id="8C110293YY556677K"
    )
    session.add(intent_c)
    await session.commit()
    await session.refresh(intent_c)

    session.add(LedgerEntry(
        transfer_id=uuid4(),
        user_id=user.id,
        bucket_id=buckets["freedom"].id,
        amount=-2200,
        currency="USD",
        state="posted",
        entry_kind="merchant_spend",
        counterparty_bucket="paypal_merchant",
        memo="Indie concert ticket",
        intent_id=intent_c.id,
        paypal_order_id="8C110293YY556677K",
        paypal_capture_id="CAPTURE-TM-882200",
        idempotency_key=f"test:seed:spend:free:2:{uuid4()}",
        created_at=now - timedelta(days=1),
        posted_at=now - timedelta(days=1)
    ))

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
