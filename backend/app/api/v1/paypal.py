"""
PayPal Balance Detection & Synchronization Router
=================================================
Exposes:
- `GET /api/v1/paypal/balance`: Queries PayPal Sandbox Reporting API (`GET /v1/reporting/balances`)
  for the user's liquid account balance.
- `POST /api/v1/paypal/sync-balance`: Detects PayPal account balance, reconciles the local
  double-entry ledger, and allocates funds across the 5 Trinity buckets according to the
  user's configured policy.
"""

from typing import Any, Dict, Optional
from fastapi import APIRouter, Body, Depends
from pydantic import BaseModel
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.user import User
from app.api.v1.auth import get_current_user
from app.ledger.engine import LedgerEngine
from app.services.paypal_client import paypal_client
from app.jobs.lifecycles import run_midnight_rollover, run_payday_allocation

router = APIRouter(prefix="/paypal", tags=["PayPal Balance & Sync"])


class PayPalSyncRequest(BaseModel):
    override_balance_cents: Optional[int] = None


class PaydayTriggerRequest(BaseModel):
    gross_income_cents: int
    dispatch_vault_payout: bool = True


class RolloverTriggerRequest(BaseModel):
    sweep_surplus_to_vault: bool = False


@router.get("/balance")
async def get_paypal_account_balance(
    user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Query PayPal Sandbox Reporting API (`GET /v1/reporting/balances`) for account balance."""
    return await paypal_client.get_account_balance(currency="USD")


@router.post("/sync-balance")
async def sync_paypal_account_balance(
    body: Optional[PayPalSyncRequest] = Body(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """
    Detect actual PayPal account balance and synchronize all 5 Trinity buckets
    via zero-sum double-entry transfers according to the user's BudgetPolicy.
    """
    paypal_balance = await paypal_client.get_account_balance(currency="USD")
    target_cents = (
        body.override_balance_cents
        if body and body.override_balance_cents is not None
        else paypal_balance["available_cents"]
    )

    updated_balances = await LedgerEngine.sync_and_allocate_buckets(
        session=session,
        user_id=user.id,
        target_total_cents=target_cents,
    )

    buckets_list = [
        {
            "kind": kind,
            "name": data["name"],
            "available": data["available"],
            "held": data["held"],
            "pending_paypal": 0,
        }
        for kind, data in updated_balances.items()
    ]

    return {
        "status": "synced",
        "paypal_balance": {
            **paypal_balance,
            "synced_cents": target_cents,
        },
        "buckets": buckets_list,
    }


@router.post("/rollover")
async def trigger_midnight_rollover(
    body: Optional[RolloverTriggerRequest] = Body(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Execute the Midnight Rollover lifecycle for the authenticated user."""
    sweep = body.sweep_surplus_to_vault if body else False
    return await run_midnight_rollover(
        session=session,
        user_id=user.id,
        sweep_surplus_to_vault=sweep,
    )


@router.post("/payday")
async def trigger_payday_allocation(
    body: PaydayTriggerRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Dict[str, Any]:
    """Execute the Payday Inflow & Automated Vault Payout lifecycle."""
    return await run_payday_allocation(
        session=session,
        user_id=user.id,
        gross_income_cents=body.gross_income_cents,
        dispatch_vault_payout=body.dispatch_vault_payout,
    )
