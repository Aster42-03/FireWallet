from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from sqlmodel import SQLModel, Field

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

# ------------------------------------------------------------------------------
# PayPal Webhook Event Model
# ------------------------------------------------------------------------------
class PayPalWebhookEventBase(SQLModel):
    event_id: str = Field(description="PayPal event ID e.g. WH-...")
    event_type: str = Field(index=True, description="Event type name e.g. PAYMENT.CAPTURE.COMPLETED")
    payload_json: str = Field(description="Raw PayPal webhook payload in JSON")
    intent_id: Optional[UUID] = Field(default=None, index=True, description="Associated intent ID if mapped")

class PayPalWebhookEvent(PayPalWebhookEventBase, table=True):
    __tablename__ = "paypal_webhook_events"
    
    event_id: str = Field(primary_key=True, description="PayPal webhook event UUID/identifier")
    processed_at: datetime = Field(default_factory=utc_now)

class PayPalWebhookEventRead(PayPalWebhookEventBase):
    processed_at: datetime
