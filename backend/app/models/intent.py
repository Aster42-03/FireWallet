from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

# ------------------------------------------------------------------------------
# Spend Intent (SQLModel Table)
# ------------------------------------------------------------------------------
class IntentBase(SQLModel):
    utterance: str = Field(description="Natural language reason for spending")
    amount: int = Field(gt=0, description="Amount in minor units (cents)")
    currency: str = Field(default="USD", max_length=3)
    merchant_name: Optional[str] = None
    category: Optional[str] = None
    necessity: Optional[str] = Field(default=None, index=True)  # 'bill', 'daily_living', 'freedom', 'ambiguous'
    recommended_bucket: Optional[str] = None  # 'bank', 'daily', 'freedom', 'vault', 'bills'
    source_bucket_id: Optional[UUID] = None
    status: str = Field(default="draft", index=True)  # draft, parsed, allowed, needs_override, hold, executing, settled, failed
    client_idempotency_key: Optional[str] = Field(default=None, index=True)
    paypal_order_id: Optional[str] = Field(default=None, index=True)

class Intent(IntentBase, table=True):
    __tablename__ = "intents"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)
    updated_at: datetime = Field(default_factory=utc_now)

class IntentRead(IntentBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

# ------------------------------------------------------------------------------
# Agent Run Audit Record
# ------------------------------------------------------------------------------
class AgentRunBase(SQLModel):
    kind: str = Field(default="intent", index=True)  # 'intent' or 'insights'
    intent_id: Optional[UUID] = Field(default=None, foreign_key="intents.id", index=True)
    thread_id: Optional[UUID] = Field(default=None, index=True)
    model: str
    prompt_version: str = "v1"
    latency_ms: int = Field(default=0)
    raw_response: Optional[str] = None
    parsed: Optional[str] = None
    error: Optional[str] = None

class AgentRun(AgentRunBase, table=True):
    __tablename__ = "agent_runs"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)

class AgentRunRead(AgentRunBase):
    id: UUID
    created_at: datetime

# ------------------------------------------------------------------------------
# Escape Window Override
# ------------------------------------------------------------------------------
class OverrideBase(SQLModel):
    intent_id: UUID = Field(foreign_key="intents.id", unique=True, index=True)
    body: str = Field(description="User written confession")
    status: str = Field(default="pending", index=True)  # pending, ready, approved, rejected, expired
    ready_at: datetime = Field(index=True)

class Override(OverrideBase, table=True):
    __tablename__ = "overrides"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)

class OverrideRead(OverrideBase):
    id: UUID
    user_id: UUID
    created_at: datetime
