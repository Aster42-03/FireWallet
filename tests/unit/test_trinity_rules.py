from uuid import uuid4
import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.ledger.engine import LedgerEngine
from app.models.user import User
from app.models.bucket import Bucket
from app.models.intent import Intent

@pytest.mark.unit
async def test_bucket_balances_calculation(seeded_session: AsyncSession):
    """Verify LedgerEngine calculates available, posted, and held balances across all 5 buckets."""
    user = (await seeded_session.exec(select(User))).first()
    assert user is not None

    balances = await LedgerEngine.get_bucket_balances(seeded_session, user.id)
    assert "bank" in balances
    assert "daily" in balances
    assert "freedom" in balances
    assert "vault" in balances
    assert "bills" in balances

    assert balances["bank"]["available"] == 80000     # $800.00
    assert balances["daily"]["available"] == 5200     # $52.00
    assert balances["freedom"]["available"] == 9000   # $90.00
    assert balances["vault"]["available"] == 20000    # $200.00
    assert balances["bills"]["available"] == 120000   # $1,200.00

@pytest.mark.unit
async def test_can_spend_negative_or_zero_amount(seeded_session: AsyncSession):
    """Verify zero or negative spend amounts are rejected immediately."""
    user = (await seeded_session.exec(select(User))).first()
    allowed, status, rationale = await LedgerEngine.can_spend(
        session=seeded_session,
        user_id=user.id,
        amount_minor=0,
        source_kind="daily",
        necessity="daily_living"
    )
    assert not allowed
    assert status == "denied"
    assert "positive" in rationale.lower()

@pytest.mark.unit
async def test_can_spend_rule_1_vault_is_locked(seeded_session: AsyncSession):
    """Rule 1: Direct spend from Vault savings is strictly forbidden under all circumstances."""
    user = (await seeded_session.exec(select(User))).first()
    allowed, status, rationale = await LedgerEngine.can_spend(
        session=seeded_session,
        user_id=user.id,
        amount_minor=5000,
        source_kind="vault",
        necessity="daily_living"
    )
    assert not allowed
    assert status == "denied"
    assert "vault is locked" in rationale.lower()

@pytest.mark.unit
async def test_can_spend_rule_2_bills_is_reserved(seeded_session: AsyncSession):
    """Rule 2: Bills bucket is reserved for fixed obligations; discretionary spend is denied."""
    user = (await seeded_session.exec(select(User))).first()
    allowed, status, rationale = await LedgerEngine.can_spend(
        session=seeded_session,
        user_id=user.id,
        amount_minor=3000,
        source_kind="bills",
        necessity="freedom"
    )
    assert not allowed
    assert status == "denied"
    assert "bills bucket is strictly reserved" in rationale.lower()

@pytest.mark.unit
async def test_can_spend_rule_3_daily_insufficient_fallback(seeded_session: AsyncSession):
    """Rule 3: Daily spend exceeding available balance cannot proceed without an Escape Window override."""
    user = (await seeded_session.exec(select(User))).first()
    # Daily currently has $52.00 (5200 cents). Attempt to spend $70.00 (7000 cents).
    allowed, status, rationale = await LedgerEngine.can_spend(
        session=seeded_session,
        user_id=user.id,
        amount_minor=7000,
        source_kind="daily",
        necessity="daily_living"
    )
    assert not allowed
    assert status == "needs_override"
    assert "insufficient funds in daily" in rationale.lower()

@pytest.mark.unit
async def test_can_spend_rule_4_bank_requires_override(seeded_session: AsyncSession):
    """Rule 4: Dipping directly into Bank foundation for discretionary spend requires an approved override."""
    user = (await seeded_session.exec(select(User))).first()

    # Without approved override -> blocked
    allowed, status, rationale = await LedgerEngine.can_spend(
        session=seeded_session,
        user_id=user.id,
        amount_minor=10000,
        source_kind="bank",
        necessity="freedom",
        has_approved_override=False
    )
    assert not allowed
    assert status == "needs_override"
    assert "escape window override required" in rationale.lower()

    # With approved override -> allowed
    allowed_ovr, status_ovr, _ = await LedgerEngine.can_spend(
        session=seeded_session,
        user_id=user.id,
        amount_minor=10000,
        source_kind="bank",
        necessity="freedom",
        has_approved_override=True
    )
    assert allowed_ovr
    assert status_ovr == "allowed"

@pytest.mark.unit
async def test_can_spend_rule_5_freedom_envelope_allowed(seeded_session: AsyncSession):
    """Rule 5: Guilt-free discretionary hedonism from Freedom envelope proceeds when balance suffices."""
    user = (await seeded_session.exec(select(User))).first()
    # Freedom currently has $90.00. Spend $25.00 for dining/drinks.
    allowed, status, rationale = await LedgerEngine.can_spend(
        session=seeded_session,
        user_id=user.id,
        amount_minor=2500,
        source_kind="freedom",
        necessity="freedom"
    )
    assert allowed
    assert status == "allowed"

@pytest.mark.unit
async def test_hold_lifecycle(seeded_session: AsyncSession):
    """Test full atomic hold lifecycle: place hold -> check debited available -> settle posted."""
    user = (await seeded_session.exec(select(User))).first()
    stmt_b = select(Bucket).where(Bucket.user_id == user.id).where(Bucket.kind == "daily")
    bucket = (await seeded_session.exec(stmt_b)).first()

    # 1. Create a dummy intent
    intent = Intent(
        user_id=user.id,
        utterance="Weekly groceries",
        amount=2000,
        source_bucket_id=bucket.id
    )
    seeded_session.add(intent)
    await seeded_session.commit()
    await seeded_session.refresh(intent)

    # Initial available was 5200 cents ($52.00)
    bal_before = await LedgerEngine.get_bucket_balances(seeded_session, user.id)
    assert bal_before["daily"]["available"] == 5200
    assert bal_before["daily"]["held"] == 0

    # 2. Place Hold for $20.00 (2000 cents)
    hold = await LedgerEngine.place_hold(
        session=seeded_session,
        user_id=user.id,
        bucket_id=bucket.id,
        amount_minor=2000,
        intent_id=intent.id
    )
    assert hold.state == "hold"
    assert hold.amount == -2000

    bal_during = await LedgerEngine.get_bucket_balances(seeded_session, user.id)
    assert bal_during["daily"]["held"] == 2000
    assert bal_during["daily"]["available"] == 3200  # 5200 - 2000 = 3200

    # 3. Settle Hold with mock PayPal capture ID
    settled = await LedgerEngine.settle_hold(
        session=seeded_session,
        intent_id=intent.id,
        paypal_capture_id="CAPTURE-TEST-9988"
    )
    assert settled is not None
    assert settled.state == "posted"
    assert settled.paypal_capture_id == "CAPTURE-TEST-9988"

    bal_after = await LedgerEngine.get_bucket_balances(seeded_session, user.id)
    assert bal_after["daily"]["held"] == 0
    assert bal_after["daily"]["posted"] == 3200
    assert bal_after["daily"]["available"] == 3200
