"""
Batch Payment Item SQLModel Model
=================================
Persists queued, approved, paid, and vetoed payment items for The Trinity
Batch Dispatcher adhering to the Tripartite SQLModel pattern and zero-float
integer minor-unit rule.
"""

from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field

def utc_now() -> datetime:
    """Returns current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

class BatchPaymentItemBase(SQLModel):
    title: str = Field(default="", description="Name of the bill or obligation (e.g., 'Apartment Rent')")
    amount_minor: int = Field(gt=0, description="Amount in integer minor units (cents)")
    category: str = Field(default="Bills", description="Category of the expense (e.g., 'Rent', 'Utilities')")
    currency: str = Field(default="USD", max_length=3, description="ISO-4217 currency code")
    source_bucket: str = Field(default="bills", description="Source reserve bucket: 'bills' or 'vault'")
    status: str = Field(
        default="pending_approval",
        index=True,
        description="'pending_approval', 'approved', 'executing', 'paid', 'vetoed', 'failed'"
    )
    recommended: bool = Field(default=True, description="True if AI coach recommends paying this batch item")
    recipient_email: Optional[str] = Field(default=None, description="PayPal recipient email for Payouts")
    payee_email: Optional[str] = Field(default=None, description="Alias for recipient_email")
    recipient_name: Optional[str] = Field(default=None, description="Alias for title / payee name")
    paypal_payout_id: Optional[str] = Field(default=None, index=True, description="PayPal Payout item/batch identifier")
    paypal_payout_item_id: Optional[str] = Field(default=None, index=True, description="PayPal Payout item identifier")
    sender_batch_id: Optional[str] = Field(default=None, index=True, description="Deterministic idempotent batch ID")
    error_message: Optional[str] = Field(default=None, description="Error explanation if payout failed")
    intent_id: Optional[UUID] = Field(default=None, foreign_key="intents.id", index=True, description="Optional linked Spend Intent")
    note: Optional[str] = Field(default=None, description="Optional note or utterance describing the batch item")

class BatchPaymentItem(BatchPaymentItemBase, table=True):
    __tablename__ = "batch_payment_items"

    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    bill_id: Optional[UUID] = Field(default=None, foreign_key="bills.id", index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now, index=True)
    paid_at: Optional[datetime] = Field(default=None, index=True)

    def __init__(self, **data):
        super().__init__(**data)
        if self.amount_minor is not None and self.amount_minor <= 0:
            raise ValueError("amount_minor must be > 0")
        if not self.title and self.recipient_name:
            self.title = self.recipient_name
        if not self.recipient_name and self.title:
            self.recipient_name = self.title
        if not self.recipient_email and self.payee_email:
            self.recipient_email = self.payee_email
        if not self.payee_email and self.recipient_email:
            self.payee_email = self.recipient_email
        if not self.paypal_payout_id and self.paypal_payout_item_id:
            self.paypal_payout_id = self.paypal_payout_item_id
        if not self.paypal_payout_item_id and self.paypal_payout_id:
            self.paypal_payout_item_id = self.paypal_payout_id

class BatchPaymentItemRead(BatchPaymentItemBase):
    id: UUID
    user_id: UUID
    bill_id: Optional[UUID] = None
    intent_id: Optional[UUID] = None
    created_at: datetime
    updated_at: datetime
    paid_at: Optional[datetime] = None
