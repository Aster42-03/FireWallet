from datetime import date
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field

# ------------------------------------------------------------------------------
# Fixed Bill Model (SQLModel Table)
# ------------------------------------------------------------------------------
class BillBase(SQLModel):
    name: str = Field(description="Name of bill (e.g. Rent, Water)")
    amount: int = Field(gt=0, description="Amount in minor units (cents)")
    currency: str = Field(default="USD", max_length=3)
    priority: int = Field(default=1, index=True, description="1 = highest priority (Rent first)")
    due_date: date = Field(index=True)
    payee_email: str = Field(description="PayPal sandbox recipient email")
    status: str = Field(default="scheduled", index=True)  # scheduled, paying, paid, blocked_insufficient, canceled
    last_payout_batch_id: Optional[str] = None

class Bill(BillBase, table=True):
    __tablename__ = "bills"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)

class BillRead(BillBase):
    id: UUID
    user_id: UUID
