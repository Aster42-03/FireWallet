import asyncio
from datetime import datetime, timezone, date, timedelta
from uuid import uuid4
from sqlmodel import select

from app.database import async_session_factory, init_db, engine
from app.models.user import User, BudgetPolicy
from app.models.bucket import Bucket
from app.models.ledger import LedgerEntry
from app.models.bill import Bill

async def seed_demo_data():
    print("Initializing database...")
    await init_db()

    async with async_session_factory() as session:
        # Check if user already exists
        stmt = select(User).limit(1)
        res = await session.exec(stmt)
        if res.first():
            print("Database already contains seed data. Skipping.")
            return

        print("Seeding demo user Aster...")
        user = User(
            email="demo-user@sandbox.paypal.com",
            display_name="Aster (Demo)",
            timezone="America/New_York"
        )
        session.add(user)
        await session.commit()
        await session.refresh(user)

        # Policy
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

        # 5 Trinity Buckets
        bucket_defs = [
            ("bank", "Bank Foundation"),
            ("daily", "Daily Allowance"),
            ("freedom", "Freedom Envelope"),
            ("vault", "Locked Savings Vault"),
            ("bills", "Reserved Bills")
        ]
        buckets = {}
        for kind, name in bucket_defs:
            b = Bucket(user_id=user.id, kind=kind, name=name)
            session.add(b)
            await session.commit()
            await session.refresh(b)
            buckets[kind] = b

        # Initial Balances (Double-Entry Ledger)
        initial_balances = [
            (buckets["bank"], 80000, "Initial Payday Remainder"),
            (buckets["daily"], 5200, "Daily Allowance with $12 Rollover"),
            (buckets["freedom"], 9000, "October Freedom Balance"),
            (buckets["vault"], 20000, "Payday 20% Skim"),
            (buckets["bills"], 120000, "November Rent Reserve")
        ]

        for b, amount, note in initial_balances:
            entry = LedgerEntry(
                transfer_id=uuid4(),
                user_id=user.id,
                bucket_id=b.id,
                amount=amount,
                currency="USD",
                state="posted",
                idempotency_key=f"seed:{b.kind}:{uuid4()}",
                posted_at=datetime.now(timezone.utc) - timedelta(days=1)
            )
            session.add(entry)

        # Scheduled Bills
        rent_bill = Bill(
            user_id=user.id,
            name="November Rent",
            amount=120000,
            due_date=date.today() + timedelta(days=3),
            payee_email="landlord@sandbox.paypal.com",
            priority=1,
            status="scheduled"
        )
        water_bill = Bill(
            user_id=user.id,
            name="Water Utility",
            amount=4500,
            due_date=date.today() + timedelta(days=10),
            payee_email="water-dept@sandbox.paypal.com",
            priority=2,
            status="scheduled"
        )
        session.add(rent_bill)
        session.add(water_bill)

        await session.commit()
        print("Demo seed complete! Balances and Trinity buckets ready.")
    await engine.dispose()

if __name__ == "__main__":
    asyncio.run(seed_demo_data())
