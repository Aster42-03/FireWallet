from datetime import datetime, timezone
from typing import Optional
from uuid import UUID, uuid4
from sqlmodel import SQLModel, Field, Relationship

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

# ------------------------------------------------------------------------------
# User Model (SQLModel Table + Schema)
# ------------------------------------------------------------------------------
class UserBase(SQLModel):
    email: str = Field(unique=True, index=True, description="Primary user email")
    display_name: str = Field(default="Demo User", description="Public display name")
    timezone: str = Field(default="America/New_York", description="IANA timezone identifier")

class User(UserBase, table=True):
    __tablename__ = "users"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True, index=True)
    created_at: datetime = Field(default_factory=utc_now)

class UserRead(UserBase):
    id: UUID
    created_at: datetime

# ------------------------------------------------------------------------------
# Budget Policy Model
# ------------------------------------------------------------------------------
class BudgetPolicyBase(SQLModel):
    currency: str = Field(default="USD", max_length=3)
    vault_skim_bps: int = Field(default=2000, ge=0, le=10000, description="Basis points skimmed to Vault (2000 = 20%)")
    daily_amount: int = Field(default=4000, ge=0, description="Target Daily balance in minor units (cents)")
    freedom_monthly_amount: int = Field(default=15000, ge=0, description="Monthly fun envelope in cents")
    bank_spend_requires_override: bool = Field(default=True)
    vault_spend_allowed: bool = Field(default=False)
    override_min_chars: int = Field(default=200, ge=50)
    override_cooldown_seconds: int = Field(default=180, ge=10)
    partner_required_for_bank: bool = Field(default=False)
    freedom_leftover_sweep_to_vault: bool = Field(default=False)

class BudgetPolicy(BudgetPolicyBase, table=True):
    __tablename__ = "budget_policies"
    
    user_id: UUID = Field(foreign_key="users.id", primary_key=True, index=True)
    updated_at: datetime = Field(default_factory=utc_now)

class BudgetPolicyUpdate(SQLModel):
    currency: Optional[str] = None
    vault_skim_bps: Optional[int] = None
    daily_amount: Optional[int] = None
    freedom_monthly_amount: Optional[int] = None
    bank_spend_requires_override: Optional[bool] = None
    vault_spend_allowed: Optional[bool] = None
    override_min_chars: Optional[int] = None
    override_cooldown_seconds: Optional[int] = None
    partner_required_for_bank: Optional[bool] = None
    freedom_leftover_sweep_to_vault: Optional[bool] = None

# ------------------------------------------------------------------------------
# Accountability Partner Links
# ------------------------------------------------------------------------------
class PartnerLinkBase(SQLModel):
    partner_email: str = Field(index=True, description="Accountability partner email")
    active: bool = Field(default=True)

class PartnerLink(PartnerLinkBase, table=True):
    __tablename__ = "partner_links"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: UUID = Field(foreign_key="users.id", index=True)
    created_at: datetime = Field(default_factory=utc_now)

class PartnerLinkRead(PartnerLinkBase):
    id: UUID
    user_id: UUID
    created_at: datetime

class PartnerApprovalBase(SQLModel):
    override_id: UUID = Field(index=True)
    partner_link_id: UUID = Field(foreign_key="partner_links.id", index=True)
    status: str = Field(default="pending", index=True)  # pending, approved, rejected

class PartnerApproval(PartnerApprovalBase, table=True):
    __tablename__ = "partner_approvals"
    
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    token_hash: str = Field(index=True)
    decided_at: Optional[datetime] = None

class PartnerApprovalRead(PartnerApprovalBase):
    id: UUID
    token_hash: str
    decided_at: Optional[datetime] = None
