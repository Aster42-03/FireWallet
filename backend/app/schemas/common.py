from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

# User & Policy
class PolicyUpdate(BaseModel):
    vault_skim_bps: Optional[int] = Field(default=None, ge=0, le=10000)
    daily_amount: Optional[int] = Field(default=None, ge=0)
    freedom_monthly_amount: Optional[int] = Field(default=None, ge=0)
    bank_spend_requires_override: Optional[bool] = None
    vault_spend_allowed: Optional[bool] = None
    override_min_chars: Optional[int] = None
    override_cooldown_seconds: Optional[int] = None
    partner_required_for_bank: Optional[bool] = None

# Buckets
class BucketResponse(BaseModel):
    kind: str
    name: str
    available: int
    held: int
    pending_paypal: int

class BucketsSummaryResponse(BaseModel):
    currency: str
    buckets: List[BucketResponse]

# Intent
class IntentCreate(BaseModel):
    utterance: str
    amount: int = Field(gt=0, description="Amount in minor units (cents)")
    currency: str = "USD"
    merchant_name: Optional[str] = None

class IntentResponse(BaseModel):
    id: UUID
    status: str
    category: Optional[str] = None
    necessity: Optional[str] = None
    recommended_bucket: Optional[str] = None
    confidence: Optional[float] = None
    rationale: Optional[str] = None
    flags: List[str] = []
    source_bucket: Optional[str] = None
    balances_after_preview: Dict[str, Any] = {}
    override_required: bool = False

class IntentExecuteResponse(BaseModel):
    status: str
    paypal_order_id: Optional[str] = None
    approval_url: Optional[str] = None

class IntentCaptureRequest(BaseModel):
    paypal_order_id: str
    payer_id: Optional[str] = None

# Overrides
class OverrideCreate(BaseModel):
    intent_id: UUID
    body: str

class OverrideResponse(BaseModel):
    id: UUID
    status: str
    ready_at: str
    cooldown_seconds: int
    partner_required: bool

# Coach & Analytics
class CoachMessageRequest(BaseModel):
    thread_id: Optional[UUID] = None
    utterance: str
    chart_id: Optional[str] = None
    filter_context: Optional[Dict[str, Any]] = None

class CoachMessageResponse(BaseModel):
    thread_id: UUID
    message_id: UUID
    reply: str
    citations: Optional[Dict[str, Any]] = None
    suggest_intent: Optional[Dict[str, Any]] = None

class DeepLedgerItem(BaseModel):
    id: UUID
    transfer_id: UUID
    created_at: str
    category: Optional[str] = None
    bucket: str
    amount: int
    state: str
    direction: Optional[str] = "DEBIT"
    entry_kind: Optional[str] = "standard"
    counterparty_bucket: Optional[str] = None
    memo: Optional[str] = None
    running_balance: Optional[int] = 0
    is_internal_transfer: Optional[bool] = False
    necessity: Optional[str] = None
    utterance: Optional[str] = None
    merchant: Optional[str] = None
    paypal_order_id: Optional[str] = None
    paypal_capture_id: Optional[str] = None

class DeepLedgerResponse(BaseModel):
    total_count: int
    items: List[DeepLedgerItem]
    aggregates: Dict[str, Any]
