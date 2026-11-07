from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field

# ------------------------------------------------------------------------------
# Trinity Bucket Model (SQLModel Table)
# ------------------------------------------------------------------------------
class BucketBase(SQLModel):
    kind: str = Field(index=True, description="Bucket type: bank, daily, freedom, vault, bills")
    name: str = Field(default="", description="Display name for the bucket")

class Bucket(BucketBase, table=True):
    __tablename__ = "buckets"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)

class BucketRead(BucketBase):
    id: UUID
    user_id: UUID
    available: int = 0
    held: int = 0
    pending_paypal: int = 0
