from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

# ------------------------------------------------------------------------------
# Double-Entry Ledger Entry (SQLModel Table)
# ------------------------------------------------------------------------------
class LedgerEntryBase(SQLModel):
    amount: int = Field(index=True, description="Signed minor units (+ credit, - debit)")
    currency: str = Field(default="USD", max_length=3)
    state: str = Field(default="posted", index=True, description="'hold', 'posted', 'released'")
    paypal_order_id: Optional[str] = Field(default=None, index=True)
    paypal_capture_id: Optional[str] = Field(default=None, index=True)
    paypal_payout_item_id: Optional[str] = Field(default=None, index=True)

class LedgerEntry(LedgerEntryBase, table=True):
    __tablename__ = "ledger_entries"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    transfer_id: UUID = Field(index=True, description="Groups balanced legs of a single transaction")
    user_id: UUID = Field(foreign_key="users.id", index=True)
    bucket_id: UUID = Field(foreign_key="buckets.id", index=True)
    intent_id: Optional[UUID] = Field(default=None, foreign_key="intents.id", index=True)
    bill_id: Optional[UUID] = Field(default=None, foreign_key="bills.id", index=True)
    idempotency_key: str = Field(unique=True, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    posted_at: Optional[datetime] = Field(default=None, index=True)

class LedgerEntryRead(LedgerEntryBase):
    id: UUID
    transfer_id: UUID
    user_id: UUID
    bucket_id: UUID
    intent_id: Optional[UUID] = None
    bill_id: Optional[UUID] = None
    idempotency_key: str
    created_at: datetime
    posted_at: Optional[datetime] = None
