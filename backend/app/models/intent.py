"""
Spend Intent, Agent Run Audit & Escape Window Override Models
=============================================================
Defines SQLModel tables for tracking spend intents, AI classification runs,
short summary tags for RAG retrieval, and high-friction/emergency overrides.
"""

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
    short_tag: Optional[str] = Field(
        default=None,
        index=True,
        max_length=80,
        description="Concise 2-5 word summary tag (e.g. 'groceries', 'takeout', 'gift for family') for user review and Coach RAG"
    )
    amount: int = Field(gt=0, description="Amount in minor units (cents)")
    currency: str = Field(default="USD", max_length=3)
    merchant_name: Optional[str] = None
    category: Optional[str] = None
    necessity: Optional[str] = Field(default=None, index=True)  # 'bill', 'daily_living', 'freedom', 'ambiguous'
    recommended_bucket: Optional[str] = None  # 'bank', 'daily', 'freedom', 'vault', 'bills'
    source_bucket_id: Optional[UUID] = None
    is_emergency: bool = Field(default=False, description="True if evaluated as a valid life/medical/safety emergency")
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
    kind: str = Field(default="intent", index=True)  # 'intent', 'insights', or 'override'
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
    body: str = Field(description="User written confession or emergency explanation")
    short_tag: Optional[str] = Field(
        default=None,
        index=True,
        max_length=80,
        description="Concise 2-5 word summary tag of override reason for RAG context"
    )
    is_emergency: bool = Field(
        default=False,
        description="True if verified as a genuine emergency (grants 0s cooldown)"
    )
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
