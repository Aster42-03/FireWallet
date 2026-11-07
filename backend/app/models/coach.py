from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

# ------------------------------------------------------------------------------
# Coach Thread Model
# ------------------------------------------------------------------------------
class CoachThreadBase(SQLModel):
    title: str = Field(default="Conversation with Coach", description="Thread conversation subject")

class CoachThread(CoachThreadBase, table=True):
    __tablename__ = "coach_threads"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)

class CoachThreadRead(CoachThreadBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime

# ------------------------------------------------------------------------------
# Coach Message Model
# ------------------------------------------------------------------------------
class CoachMessageBase(SQLModel):
    role: str = Field(description="Message role: 'user', 'assistant', 'system', or 'tool'")
    content: str = Field(description="Message text body or coaching explanation")
    chart_id: Optional[str] = Field(default=None, description="Referenced UI chart identifier")
    citations_json: Optional[str] = Field(default=None, description="Serialized JSON array of data citations")
    suggest_intent_json: Optional[str] = Field(default=None, description="Serialized suggested intent payload")

class CoachMessage(CoachMessageBase, table=True):
    __tablename__ = "coach_messages"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    thread_id: UUID = Field(foreign_key="coach_threads.id", index=True)
    created_at: datetime = Field(default_factory=utc_now, index=True)

class CoachMessageRead(CoachMessageBase):
    id: UUID
    thread_id: UUID
    created_at: datetime
