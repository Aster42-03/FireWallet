from datetime import datetime, timezone
from uuid import uuid4
import pytest
from pydantic import ValidationError

from app.models.user import User, BudgetPolicy, UserRead, BudgetPolicyBase
from app.models.bucket import Bucket, BucketRead
from app.models.ledger import LedgerEntry, LedgerEntryRead
from app.models.intent import Intent, IntentRead, Override, AgentRun
from app.models.bill import Bill, BillRead
from app.models.coach import CoachThread, CoachMessage
from app.models.webhook import PayPalWebhookEvent

@pytest.mark.unit
def test_user_and_policy_model_dump():
    """Verify modern SQLModel Pydantic v2 .model_dump() serialization."""
    user = User(
        email="aster@sandbox.paypal.com",
        display_name="Aster Unit",
        timezone="America/New_York"
    )
    user_dict = user.model_dump()
    assert user_dict["email"] == "aster@sandbox.paypal.com"
    assert user_dict["display_name"] == "Aster Unit"
    assert isinstance(user.created_at, datetime)
    assert user.created_at.tzinfo is not None  # Timezone-aware UTC

    policy = BudgetPolicy(
        user_id=user.id,
        vault_skim_bps=2000,
        daily_amount=4000
    )
    p_dict = policy.model_dump()
    assert p_dict["vault_skim_bps"] == 2000
    assert p_dict["daily_amount"] == 4000

@pytest.mark.unit
def test_budget_policy_validation_constraints():
    """Verify basis points cannot exceed 100% (10,000 bps) or fall below 0."""
    # Valid
    valid_p = BudgetPolicyBase(vault_skim_bps=5000)
    assert valid_p.vault_skim_bps == 5000

    # Invalid: > 10000
    with pytest.raises(ValidationError):
        BudgetPolicyBase(vault_skim_bps=12000)

    # Invalid: < 0
    with pytest.raises(ValidationError):
        BudgetPolicyBase(vault_skim_bps=-50)

@pytest.mark.unit
def test_zero_float_accounting_invariants():
    """Verify monetary amounts are strictly 64-bit integer minor units (cents)."""
    # Valid integer cents
    bill = Bill(
        user_id=uuid4(),
        name="Internet Bill",
        amount=6500,  # $65.00
        due_date=datetime.now(timezone.utc).date(),
        payee_email="isp@sandbox.paypal.com"
    )
    assert isinstance(bill.amount, int)
    assert bill.amount == 6500

    # Validation error for negative amount on BillBase
    with pytest.raises(ValidationError):
        BillBase(
            name="Negative Bill",
            amount=-500,  # gt=0 constraint
            due_date=datetime.now(timezone.utc).date(),
            payee_email="isp@sandbox.paypal.com"
        )

@pytest.mark.unit
def test_ledger_entry_serialization():
    """Verify double-entry ledger entry attributes and DTO reading."""
    transfer_id = uuid4()
    entry = LedgerEntry(
        transfer_id=transfer_id,
        user_id=uuid4(),
        bucket_id=uuid4(),
        amount=-2400,
        currency="USD",
        state="hold",
        idempotency_key=f"test:{uuid4()}"
    )
    dump = entry.model_dump()
    assert dump["amount"] == -2400
    assert dump["state"] == "hold"
    assert dump["currency"] == "USD"

@pytest.mark.unit
def test_paypal_webhook_event_model():
    """Verify webhook event table stores raw JSON payload and event ID."""
    evt = PayPalWebhookEvent(
        event_id="WH-99887766",
        event_type="PAYMENT.CAPTURE.COMPLETED",
        payload_json='{"id": "WH-99887766", "summary": "Payment completed"}'
    )
    dump = evt.model_dump()
    assert dump["event_id"] == "WH-99887766"
    assert dump["event_type"] == "PAYMENT.CAPTURE.COMPLETED"
    assert dump["processed_at"] is not None
