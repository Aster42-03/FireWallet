import asyncio
from datetime import datetime, timezone, date, timedelta
from uuid import uuid4
from sqlmodel import select

from app.database import async_session_factory, init_db, engine
from app.models.user import User, BudgetPolicy
from app.models.bucket import Bucket
from app.models.ledger import LedgerEntry
from app.models.bill import Bill
from app.models.intent import Intent

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

        # Initial Balances (Bank-Kept Double-Entry Ledger System)
        now = datetime.now(timezone.utc)
        
        # 1. External Payday Income into Bank Foundation
        payday_transfer_id = uuid4()
        payday_entry = LedgerEntry(
            transfer_id=payday_transfer_id,
            user_id=user.id,
            bucket_id=buckets["bank"].id,
            amount=247000,  # $2,470.00 Gross Income
            currency="USD",
            state="posted",
            entry_kind="payday_inflow",
            counterparty_bucket="external_payroll",
            memo="Bi-Weekly Payroll Direct Deposit",
            idempotency_key=f"seed:payday:{uuid4()}",
            created_at=now - timedelta(days=5),
            posted_at=now - timedelta(days=5)
        )
        session.add(payday_entry)

        # 2. Bank -> Vault (20% Automated Savings Skim: $200.00)
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
            idempotency_key=f"seed:vault:debit:{uuid4()}",
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
            idempotency_key=f"seed:vault:credit:{uuid4()}",
            created_at=now - timedelta(days=5),
            posted_at=now - timedelta(days=5)
        ))

        # 3. Bank -> Bills (November Rent Reserve: $1,200.00)
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
            idempotency_key=f"seed:bills:debit:{uuid4()}",
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
            idempotency_key=f"seed:bills:credit:{uuid4()}",
            created_at=now - timedelta(days=5),
            posted_at=now - timedelta(days=5)
        ))

        # 4. Bank -> Freedom (Monthly Freedom Allocation: $150.00)
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
            idempotency_key=f"seed:freedom:debit:{uuid4()}",
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
            idempotency_key=f"seed:freedom:credit:{uuid4()}",
            created_at=now - timedelta(days=4),
            posted_at=now - timedelta(days=4)
        ))

        # 5. Bank -> Daily (Daily Living Allowance Top-Up: $120.00)
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
            idempotency_key=f"seed:daily:debit:{uuid4()}",
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
            idempotency_key=f"seed:daily:credit:{uuid4()}",
            created_at=now - timedelta(days=3),
            posted_at=now - timedelta(days=3)
        ))

        # 6. Settled Merchant Spend from Daily (Groceries: -$44.00)
        intent_groc = Intent(
            user_id=user.id,
            utterance="Weekly groceries at Trader Joe's",
            amount=4400,
            currency="USD",
            merchant_name="Trader Joe's",
            category="groceries",
            necessity="daily_living",
            recommended_bucket="daily",
            source_bucket_id=buckets["daily"].id,
            status="settled",
            paypal_order_id="5O190127TN984224L",
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2)
        )
        session.add(intent_groc)
        await session.commit()
        await session.refresh(intent_groc)

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
            intent_id=intent_groc.id,
            paypal_order_id="5O190127TN984224L",
            paypal_capture_id="CAPTURE-TJ-998811",
            idempotency_key=f"seed:spend:daily:1:{uuid4()}",
            created_at=now - timedelta(days=2),
            posted_at=now - timedelta(days=2)
        ))

        # 7. Settled Merchant Spend from Daily (Transit: -$24.00)
        intent_transit = Intent(
            user_id=user.id,
            utterance="Subway weekly pass recharge",
            amount=2400,
            currency="USD",
            merchant_name="MTA Transit",
            category="transit",
            necessity="daily_living",
            recommended_bucket="daily",
            source_bucket_id=buckets["daily"].id,
            status="settled",
            paypal_order_id="3K281920PQ447192M",
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1)
        )
        session.add(intent_transit)
        await session.commit()
        await session.refresh(intent_transit)

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
            intent_id=intent_transit.id,
            paypal_order_id="3K281920PQ447192M",
            paypal_capture_id="CAPTURE-MTA-332211",
            idempotency_key=f"seed:spend:daily:2:{uuid4()}",
            created_at=now - timedelta(days=1),
            posted_at=now - timedelta(days=1)
        ))

        # 8. Settled Merchant Spend from Freedom (Dining: -$38.00)
        intent_dining = Intent(
            user_id=user.id,
            utterance="Dinner and drinks at Toki Ramen",
            amount=3800,
            currency="USD",
            merchant_name="Toki Ramen",
            category="eating_out",
            necessity="freedom",
            recommended_bucket="freedom",
            source_bucket_id=buckets["freedom"].id,
            status="settled",
            paypal_order_id="7B992819XX112233R",
            created_at=now - timedelta(days=2),
            updated_at=now - timedelta(days=2)
        )
        session.add(intent_dining)
        await session.commit()
        await session.refresh(intent_dining)

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
            intent_id=intent_dining.id,
            paypal_order_id="7B992819XX112233R",
            paypal_capture_id="CAPTURE-TOKI-774411",
            idempotency_key=f"seed:spend:freedom:1:{uuid4()}",
            created_at=now - timedelta(days=2),
            posted_at=now - timedelta(days=2)
        ))

        # 9. Settled Merchant Spend from Freedom (Concert ticket: -$22.00)
        intent_concert = Intent(
            user_id=user.id,
            utterance="Indie band concert ticket",
            amount=2200,
            currency="USD",
            merchant_name="Ticketmaster",
            category="entertainment",
            necessity="freedom",
            recommended_bucket="freedom",
            source_bucket_id=buckets["freedom"].id,
            status="settled",
            paypal_order_id="8C110293YY556677K",
            created_at=now - timedelta(days=1),
            updated_at=now - timedelta(days=1)
        )
        session.add(intent_concert)
        await session.commit()
        await session.refresh(intent_concert)

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
            intent_id=intent_concert.id,
            paypal_order_id="8C110293YY556677K",
            paypal_capture_id="CAPTURE-TM-882200",
            idempotency_key=f"seed:spend:freedom:2:{uuid4()}",
            created_at=now - timedelta(days=1),
            posted_at=now - timedelta(days=1)
        ))

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
