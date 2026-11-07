import os
from uuid import uuid4
from datetime import datetime, timezone

import pytest
from sqlmodel import SQLModel, select
from sqlmodel.ext.asyncio.session import AsyncSession
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from tests.conftest import is_docker_available
from app.models.user import User, BudgetPolicy
from app.models.bucket import Bucket
from app.models.ledger import LedgerEntry
from app.models.intent import Intent
from app.ledger.engine import LedgerEngine

try:
    from testcontainers.community.postgres import PostgresContainer
except ImportError:
    from testcontainers.postgres import PostgresContainer

@pytest.mark.integration
@pytest.mark.skipif(
    not is_docker_available(),
    reason="Docker daemon is not running. Start Docker to run Testcontainers PostgreSQL integration tests."
)
async def test_testcontainers_postgresql_lifecycle():
    """
    End-to-End Testcontainers Integration Test:
    Spins up an ephemeral, production-identical PostgreSQL 16 container,
    provisions the SQLModel schema using asyncpg, and executes true
    double-entry financial invariants and row locks against real PostgreSQL.
    """
    # 1. Spin up ephemeral PostgreSQL 16 container
    with PostgresContainer("postgres:16-alpine") as postgres:
        pg_url = postgres.get_connection_url(driver="asyncpg")

        # 2. Initialize SQLAlchemy 2.0 Async Engine with asyncpg
        engine = create_async_engine(pg_url, echo=False)

        # 3. Create full SQLModel schema (13 tables)
        async with engine.begin() as conn:
            await conn.run_sync(SQLModel.metadata.create_all)

        session_factory = async_sessionmaker(
            bind=engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False
        )

        async with session_factory() as session:
            # 4. Insert real PostgreSQL User with UUID primary key
            user = User(
                email="testcontainers-user@sandbox.paypal.com",
                display_name="Testcontainers Postgres Aster",
                timezone="America/New_York"
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            assert user.id is not None
            assert isinstance(user.created_at, datetime)
            assert user.created_at.tzinfo is not None

            # 5. Insert Policy
            policy = BudgetPolicy(
                user_id=user.id,
                vault_skim_bps=2000,
                daily_amount=4000,
                freedom_monthly_amount=15000
            )
            session.add(policy)

            # 6. Insert Trinity Buckets
            daily_bucket = Bucket(user_id=user.id, kind="daily", name="Daily Allowance")
            bank_bucket = Bucket(user_id=user.id, kind="bank", name="Bank Foundation")
            session.add(daily_bucket)
            session.add(bank_bucket)
            await session.commit()
            await session.refresh(daily_bucket)
            await session.refresh(bank_bucket)

            # 7. Seed initial double-entry ledger credit (BIGINT minor units)
            entry = LedgerEntry(
                transfer_id=uuid4(),
                user_id=user.id,
                bucket_id=daily_bucket.id,
                amount=6000,  # $60.00
                currency="USD",
                state="posted",
                idempotency_key=f"tc:init:{daily_bucket.id}",
                created_at=datetime.now(timezone.utc),
                posted_at=datetime.now(timezone.utc)
            )
            session.add(entry)
            await session.commit()

            # 8. Verify LedgerEngine calculations on real PostgreSQL
            balances = await LedgerEngine.get_bucket_balances(session, user.id)
            assert balances["daily"]["available"] == 6000
            assert balances["daily"]["held"] == 0

            # 9. Test Intent & Hold Placement
            intent = Intent(
                user_id=user.id,
                utterance="Lunch at Chipotle",
                amount=1500,
                source_bucket_id=daily_bucket.id
            )
            session.add(intent)
            await session.commit()
            await session.refresh(intent)

            hold = await LedgerEngine.place_hold(
                session=session,
                user_id=user.id,
                bucket_id=daily_bucket.id,
                amount_minor=1500,
                intent_id=intent.id
            )
            assert hold.state == "hold"

            balances_after_hold = await LedgerEngine.get_bucket_balances(session, user.id)
            assert balances_after_hold["daily"]["available"] == 4500
            assert balances_after_hold["daily"]["held"] == 1500

            # 10. Settle Hold against real PostgreSQL TIMESTAMPTZ column
            settled = await LedgerEngine.settle_hold(
                session=session,
                intent_id=intent.id,
                paypal_capture_id="CAPTURE-TC-POSTGRES-1234"
            )
            assert settled.state == "posted"
            assert settled.posted_at is not None

            balances_final = await LedgerEngine.get_bucket_balances(session, user.id)
            assert balances_final["daily"]["available"] == 4500
            assert balances_final["daily"]["held"] == 0

        # Clean teardown
        await engine.dispose()
