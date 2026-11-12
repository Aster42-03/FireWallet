"""
Shared Pydantic API Request & Response Schemas
==============================================
Defines strict typed contracts for Buckets, Intents, Escape Window Overrides,
the Unified Monolithic Coach Agent (`CoachDecision` & 1-tap `ActionCard`),
Short-Tag RAG metadata, and AG Grid Deep Ledger analytics.
"""

from typing import Any, Dict, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field

# ------------------------------------------------------------------------------
# User & Policy
# ------------------------------------------------------------------------------
class PolicyUpdate(BaseModel):
    vault_skim_bps: Optional[int] = Field(default=None, ge=0, le=10000)
    daily_amount: Optional[int] = Field(default=None, ge=0)
    freedom_monthly_amount: Optional[int] = Field(default=None, ge=0)
    bills_monthly_amount: Optional[int] = Field(default=None, ge=0)
    bank_spend_requires_override: Optional[bool] = None
    vault_spend_allowed: Optional[bool] = None
    override_min_chars: Optional[int] = None
    override_cooldown_seconds: Optional[int] = None
    partner_required_for_bank: Optional[bool] = None

# ------------------------------------------------------------------------------
# Buckets
# ------------------------------------------------------------------------------
class BucketResponse(BaseModel):
    kind: str
    name: str
    available: int
    held: int
    pending_paypal: int

class BucketsSummaryResponse(BaseModel):
    currency: str
    buckets: List[BucketResponse]

# ------------------------------------------------------------------------------
# Unified Agent Structured Outputs & 1-Tap Action Cards
# ------------------------------------------------------------------------------
class ActionCard(BaseModel):
    """
    Pre-configured 1-tap action button returned by Quick Intent or the Coach.
    Allows single-click PayPal checkout, Vault sweep, Batch staging, or Escape Window launch.
    """
    action_type: str = Field(
        description="'paypal_checkout', 'sweep_to_vault', 'stage_batch', 'open_override', or 'none'"
    )
    label: str = Field(description="User-facing CTA button label")
    short_tag: str = Field(description="Concise 2-5 word summary tag (e.g., 'groceries', 'takeout')")
    utterance: str
    amount_cents: int = Field(ge=0)
    currency: str = "USD"
    category: str = "general"
    necessity: str = "freedom"
    target_bucket: str = "freedom"
    merchant_name: Optional[str] = None
    intent_id: Optional[UUID] = None
    is_emergency: bool = False
    verdict: str = Field(
        default="accepted",
        description="'accepted', 'rejected', or 'refer_to_coach'"
    )

class CoachDecision(BaseModel):
    """
    Monolithic single-call LLM structured output combining conversational voice
    with deterministic action metadata and a 2-5 word RAG tag.
    """
    reply: str
    status: str = Field(
        default="info",
        description="'accepted', 'rejected', 'refer_to_coach', or 'info'"
    )
    action_type: str = Field(
        default="none",
        description="'paypal_checkout', 'sweep_to_vault', 'stage_batch', 'open_override', or 'none'"
    )
    short_tag: str = Field(
        default="general query",
        description="Concise 2-5 word summary tag for user review and RAG memory"
    )
    category: Optional[str] = None
    necessity: Optional[str] = None
    target_bucket: Optional[str] = None
    amount_cents: Optional[int] = None
    merchant_name: Optional[str] = None
    is_emergency: bool = False
    rationale: Optional[str] = None
    flags: List[str] = []

class CoachExecuteActionRequest(BaseModel):
    """Payload sent when the user taps a 1-tap ActionCard inside the Coach sidebar."""
    action_type: str = Field(description="'paypal_checkout', 'sweep_to_vault', or 'stage_batch'")
    utterance: str
    short_tag: Optional[str] = None
    amount_cents: int = Field(gt=0, description="Amount in minor units (cents)")
    currency: str = "USD"
    category: Optional[str] = None
    necessity: Optional[str] = None
    target_bucket: Optional[str] = None
    merchant_name: Optional[str] = None
    intent_id: Optional[UUID] = None
    is_emergency: bool = False
    auto_capture_demo: bool = True

class CoachExecuteActionResponse(BaseModel):
    """Result of executing a 1-tap Coach ActionCard."""
    status: str
    action_type: str
    short_tag: str
    amount_cents: int
    source_bucket: str
    destination_bucket: Optional[str] = None
    intent_id: Optional[UUID] = None
    paypal_order_id: Optional[str] = None
    paypal_capture_id: Optional[str] = None
    approval_url: Optional[str] = None
    transfer_id: Optional[UUID] = None
    message: str

# ------------------------------------------------------------------------------
# Intent Firewall
# ------------------------------------------------------------------------------
class IntentCreate(BaseModel):
    utterance: str
    amount: int = Field(gt=0, description="Amount in minor units (cents)")
    currency: str = "USD"
    merchant_name: Optional[str] = None
    short_tag: Optional[str] = None

class IntentResponse(BaseModel):
    id: UUID
    status: str
    verdict: str = "accepted"  # 'accepted', 'rejected', or 'refer_to_coach'
    amount: Optional[int] = Field(default=None, description="Intent amount in minor currency units (cents)")
    currency: str = Field(default="USD", description="Currency code (USD)")
    short_tag: Optional[str] = None
    category: Optional[str] = None
    necessity: Optional[str] = None
    recommended_bucket: Optional[str] = None
    confidence: Optional[float] = None
    rationale: Optional[str] = None
    flags: List[str] = []
    source_bucket: Optional[str] = None
    balances_after_preview: Dict[str, Any] = {}
    override_required: bool = False
    is_emergency: bool = False
    cooldown_seconds: Optional[int] = None
    action_card: Optional[ActionCard] = None

class IntentExecuteRequest(BaseModel):
    return_url: Optional[str] = None
    cancel_url: Optional[str] = None

class IntentExecuteResponse(BaseModel):
    status: str
    paypal_order_id: Optional[str] = None
    approval_url: Optional[str] = None
    short_tag: Optional[str] = None

class IntentCaptureRequest(BaseModel):
    paypal_order_id: str
    payer_id: Optional[str] = None

class IntentOrderStatusResponse(BaseModel):
    intent_id: UUID
    paypal_order_id: Optional[str] = None
    status: str
    order_status: str
    approval_url: Optional[str] = None
    payer_id: Optional[str] = None
    error: Optional[str] = None

# ------------------------------------------------------------------------------
# Escape Window Overrides
# ------------------------------------------------------------------------------
class OverrideCreate(BaseModel):
    intent_id: UUID
    body: str

class OverrideResponse(BaseModel):
    id: UUID
    status: str
    ready_at: str
    cooldown_seconds: int
    partner_required: bool
    is_emergency: bool = False
    short_tag: Optional[str] = None

# ------------------------------------------------------------------------------
# Coach & Deep Analytics
# ------------------------------------------------------------------------------
class CoachMessageRequest(BaseModel):
    thread_id: Optional[UUID] = None
    utterance: str
    chart_id: Optional[str] = None
    filter_context: Optional[Dict[str, Any]] = None

class CoachMessageResponse(BaseModel):
    thread_id: UUID
    message_id: UUID
    reply: str
    short_tag: Optional[str] = None
    decision: Optional[CoachDecision] = None
    action_card: Optional[ActionCard] = None
    citations: Optional[Dict[str, Any]] = None
    suggest_intent: Optional[Dict[str, Any]] = None
    provider: Optional[str] = None
    model: Optional[str] = None

class DeepLedgerItem(BaseModel):
    id: UUID
    transfer_id: UUID
    created_at: str
    short_tag: Optional[str] = None
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

# ------------------------------------------------------------------------------
# The Trinity Batch Dispatcher (M4)
# ------------------------------------------------------------------------------
class BatchPaymentItemDTO(BaseModel):
    id: Optional[UUID] = Field(default=None, description="Database UUID if item is already staged")
    bill_id: Optional[UUID] = Field(default=None, description="Linked bill ID if from scheduled bills")
    intent_id: Optional[UUID] = Field(default=None, description="Linked intent ID if from quick intent or chat")
    title: str = Field(description="Name of the bill or obligation, e.g., 'Apartment Rent'")
    amount_minor: int = Field(gt=0, description="Exact monetary amount in integer minor units (cents)")
    category: str = Field(default="Bills", description="Category of the expense, e.g., 'Rent', 'Utilities'")
    currency: str = Field(default="USD", description="Currency code")
    source_bucket: str = Field(default="bills", description="Source bucket: 'bills' or 'vault'")
    recommended: bool = Field(default=True, description="True if the AI strongly recommends paying this in current batch")
    recipient_email: Optional[str] = Field(default=None, description="PayPal recipient email")
    payee_email: Optional[str] = Field(default=None, description="Alias for recipient_email")
    recipient_name: Optional[str] = Field(default=None, description="Alias for title")
    due_date: Optional[str] = Field(default=None, description="Due date string if applicable")
    note: Optional[str] = Field(default=None, description="Note or description of the staged item")
    status: str = Field(default="pending_approval", description="Status of staged item")
    paypal_payout_id: Optional[str] = Field(default=None, description="PayPal Payout batch ID")
    error_message: Optional[str] = Field(default=None, description="Error reason if failed")

class BatchStageIntentRequest(BaseModel):
    intent_id: Optional[UUID] = Field(default=None, description="Optional Intent UUID to link")
    recipient_email: str = Field(description="PayPal recipient email for payout")
    amount_cents: int = Field(gt=0, description="Amount in minor units (cents)")
    currency: str = Field(default="USD", description="Currency code")
    category: str = Field(default="bills", description="Category of the expense (e.g., 'bills', 'utilities', 'rent')")
    source_bucket: str = Field(default="bills", description="Source bucket: 'bills' or 'vault'")
    note: Optional[str] = Field(default=None, description="Optional note or utterance describing the batch item")

class BatchStageIntentResponse(BaseModel):
    success: bool
    batch_item_id: UUID
    recipient_email: str
    amount_cents: int
    source_bucket: str
    status: str

class BatchDispatcherProposal(BaseModel):
    coach_message: str = Field(description="Empathetic, clear explanation of the proposed batch payment plan.")
    total_batch_amount_minor: int = Field(default=0, description="Sum of all recommended batch items in integer minor units (cents)")
    items: List[BatchPaymentItemDTO] = Field(default=[], description="List of queued obligations for user review and veto.")
    risk_assessment: Any = Field(description="Security note verifying that emergency and primary bank funds remain untouched.")
    vault_balance_minor: int = Field(default=0, description="Available balance in Vault (cents)")
    bills_balance_minor: int = Field(default=0, description="Available balance in Reserved Bills (cents)")
    safe_to_execute: bool = Field(default=True, description="True if isolated funds cover total batch")

class BatchExecuteRequest(BaseModel):
    approved_item_ids: List[UUID] = Field(description="List of approved BatchPaymentItem UUIDs")
    source_bucket: str = Field(default="bills", description="Fund source: 'bills' or 'vault'")

class BatchExecutionItemResult(BaseModel):
    item_id: UUID
    title: str
    status: str
    paypal_payout_id: Optional[str] = None
    error_message: Optional[str] = None

class BatchExecutionSummary(BaseModel):
    status: str = Field(default="completed", description="'completed', 'partial_failure', or 'failed'")
    payout_batch_id: Optional[str] = Field(default=None, description="PayPal Payout Batch ID from /v1/payments/payouts")
    batch_status: Optional[str] = Field(default=None, description="PayPal Batch Status (SUCCESS, PENDING, PROCESSING)")
    executed_count: int = Field(default=0, description="Number of successfully executed payouts")
    failed_count: int = Field(default=0, description="Number of failed payouts")
    total_amount_minor: int = Field(default=0, description="Total amount successfully executed (cents)")
    results: List[BatchExecutionItemResult] = Field(default=[], description="Item-by-item execution results")
    remaining_isolated_balance_minor: int = Field(default=0, description="Remaining balance in source bucket (cents)")
    message: str = Field(default="", description="Summary message")

class BatchStatusResponse(BaseModel):
    payout_batch_id: str
    batch_status: str  # 'SUCCESS', 'PENDING', 'PROCESSING', 'DENIED', 'CANCELED'
    time_created: Optional[str] = None
    time_completed: Optional[str] = None
    total_amount: Optional[str] = None
    fees: Optional[str] = None
    items: List[Dict[str, Any]] = []
