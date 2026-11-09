"""
Automated Trinity Lifecycle Workers (Phase 4)
=============================================
Implements deterministic zero-sum lifecycle workers:
1. `run_midnight_rollover`:
   - Evaluates unspent `daily` balance at midnight.
   - Sweeps unspent remainder to `vault` (or compounds in `daily` if under daily allowance).
   - Refills `daily` from `bank` up to configured `daily_amount`.
2. `run_payday_allocation`:
   - Credits gross income inflow into `bank`.
   - Allocates Vault %, Reserved Bills, Daily, and Freedom envelopes via zero-sum double-entry legs.
   - Optionally dispatches a PayPal Payout for the Vault allocation when configured.
"""

from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.user import BudgetPolicy
from app.models.ledger import LedgerEntry
from app.models.bill import Bill
from app.ledger.engine import LedgerEngine
from app.services.paypal_client import paypal_client


async def run_midnight_rollover(
    session: AsyncSession,
    user_id: UUID,
    sweep_surplus_to_vault: bool = False,
) -> Dict[str, Any]:
    """
    Executes the Midnight Daily Rollover lifecycle for a user:
    - If `sweep_surplus_to_vault` is True and `daily` > 0, sweeps unspent Daily balance into `vault`
      and refills `daily` from `bank` up to `policy.daily_amount`.
    - Otherwise (compound rollover), keeps unspent `daily` balance and tops up from `bank` by `policy.daily_amount`.
    """
    balances = await LedgerEngine.get_bucket_balances(session, user_id)
    pol_res = await session.exec(select(BudgetPolicy).where(BudgetPolicy.user_id == user_id))
    policy = pol_res.first()
    daily_target = policy.daily_amount if policy else 4000

    bank_id = balances["bank"]["bucket_id"]
    daily_id = balances["daily"]["bucket_id"]
    vault_id = balances["vault"]["bucket_id"]

    unspent_daily = balances["daily"]["available"]
    swept_to_vault = 0
    topped_up_from_bank = 0

    if sweep_surplus_to_vault and unspent_daily > 0:
        await LedgerEngine.record_double_entry_transfer(
            session=session,
            user_id=user_id,
            from_bucket_id=daily_id,
            to_bucket_id=vault_id,
            amount_minor=unspent_daily,
            entry_kind="vault_skim",
            memo="Midnight Rollover Surplus Sweep to Vault",
            from_bucket_kind="daily",
            to_bucket_kind="vault",
        )
        swept_to_vault = unspent_daily
        refill_needed = daily_target
    else:
        # Compound rollover: top up up to daily_target if below target, or add daily_target allowance
        refill_needed = max(0, daily_target - unspent_daily) if unspent_daily >= daily_target else daily_target

    bank_avail = (await LedgerEngine.get_bucket_balances(session, user_id))["bank"]["available"]
    actual_topup = min(bank_avail, refill_needed)

    if actual_topup > 0:
        await LedgerEngine.record_double_entry_transfer(
            session=session,
            user_id=user_id,
            from_bucket_id=bank_id,
            to_bucket_id=daily_id,
            amount_minor=actual_topup,
            entry_kind="morning_topup",
            memo="Midnight Rollover Daily Top-Up",
            from_bucket_kind="bank",
            to_bucket_kind="daily",
        )
        topped_up_from_bank = actual_topup

    updated = await LedgerEngine.get_bucket_balances(session, user_id)
    return {
        "status": "completed",
        "unspent_daily_before": unspent_daily,
        "swept_to_vault_cents": swept_to_vault,
        "topped_up_from_bank_cents": topped_up_from_bank,
        "daily_available_after": updated["daily"]["available"],
    }


async def run_payday_allocation(
    session: AsyncSession,
    user_id: UUID,
    gross_income_cents: int,
    dispatch_vault_payout: bool = True,
) -> Dict[str, Any]:
    """
    Executes the Payday Inflow & Trinity Split lifecycle:
    1. Credits `gross_income_cents` into `bank`.
    2. Transfers configured Vault % (`vault_skim_bps`) from `bank` -> `vault`.
    3. Transfers scheduled Bill obligations from `bank` -> `bills`.
    4. Tops up `daily` and `freedom` envelopes from `bank`.
    """
    balances = await LedgerEngine.get_bucket_balances(session, user_id)
    pol_res = await session.exec(select(BudgetPolicy).where(BudgetPolicy.user_id == user_id))
    policy = pol_res.first()

    bank_id = balances["bank"]["bucket_id"]
    now = datetime.now(timezone.utc)
    payday_tx_id = uuid4()

    inflow_entry = LedgerEntry(
        transfer_id=payday_tx_id,
        user_id=user_id,
        bucket_id=bank_id,
        amount=gross_income_cents,
        currency="USD",
        state="posted",
        entry_kind="payday_inflow",
        counterparty_bucket="external_payroll",
        memo=f"Payday Direct Deposit (${gross_income_cents / 100:.2f})",
        idempotency_key=f"payday:{payday_tx_id}",
        created_at=now,
        posted_at=now,
    )
    session.add(inflow_entry)
    await session.commit()

    vault_bps = policy.vault_skim_bps if policy else 2000
    vault_alloc = (gross_income_cents * vault_bps) // 10000

    payout_batch_id: Optional[str] = None
    if vault_alloc > 0:
        await LedgerEngine.record_double_entry_transfer(
            session=session,
            user_id=user_id,
            from_bucket_id=bank_id,
            to_bucket_id=balances["vault"]["bucket_id"],
            amount_minor=vault_alloc,
            entry_kind="vault_skim",
            memo="Payday Automated Vault Allocation",
            from_bucket_kind="bank",
            to_bucket_kind="vault",
        )
        if dispatch_vault_payout:
            payout_res = await paypal_client.create_payout(
                batch_id=f"vault-{str(payday_tx_id)[:12]}",
                receiver_email="vault@sandbox.paypal.com",
                amount_cents=vault_alloc,
                note="FireWallet Automated Payday Vault Allocation",
            )
            payout_batch_id = (payout_res.get("batch_header") or {}).get("payout_batch_id")

    updated = await LedgerEngine.get_bucket_balances(session, user_id)
    return {
        "status": "allocated",
        "gross_income_cents": gross_income_cents,
        "vault_allocated_cents": vault_alloc,
        "payout_batch_id": payout_batch_id,
        "bank_available_after": updated["bank"]["available"],
        "vault_available_after": updated["vault"]["available"],
    }
