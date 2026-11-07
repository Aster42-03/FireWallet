"""
FireWallet Deterministic Ledger & Trinity Policy Engine
======================================================
The core accounting engine enforcing the 5 Trinity bucket invariants:
1. Vault is locked long-term savings (spend strictly prohibited).
2. Bills bucket is reserved for contractual obligations.
3. Daily living has a hard cap with automatic positive rollover.
4. Freedom envelope is an un-rolled discretionary entertainment cap.
5. Bank Foundation direct spend requires an Escape Window override.

Accounting Invariants:
- Zero-Float: All arithmetic is strictly integer minor currency units (cents).
- Double-Entry: Internal transfers record balanced debit (-amt) and credit (+amt) legs sharing transfer_id.
- Two-Phase Spend: Hold placed prior to external checkout; settled or released upon webhook confirmation.
"""

from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.bucket import Bucket
from app.models.ledger import LedgerEntry
from app.models.user import BudgetPolicy

def utc_now() -> datetime:
    """Returns current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)

class LedgerEngine:
    """
    Stateful accounting engine querying ledger entries and evaluating spending invariants.
    """

    @staticmethod
    async def get_bucket_balances(session: AsyncSession, user_id: UUID) -> Dict[str, Dict[str, int]]:
        """
        Calculate available, held, and posted balances for each Trinity bucket.
        
        Formula:
            available = max(0, posted_sum - held_sum)
            
        Args:
            session: Active database AsyncSession.
            user_id: UUID of the user.
            
        Returns:
            Dict mapping bucket kind ('bank', 'daily', etc.) to balance breakdown in cents.
        """
        statement = select(Bucket).where(Bucket.user_id == user_id)
        result = await session.exec(statement)
        buckets = result.all()

        balances = {}
        for b in buckets:
            # Query posted entries (settled credits and debits)
            stmt_posted = (
                select(LedgerEntry.amount)
                .where(LedgerEntry.bucket_id == b.id)
                .where(LedgerEntry.state == "posted")
            )
            res_posted = await session.exec(stmt_posted)
            posted_sum = sum(res_posted.all())

            # Query active holds (in-flight PayPal checkouts)
            stmt_held = (
                select(LedgerEntry.amount)
                .where(LedgerEntry.bucket_id == b.id)
                .where(LedgerEntry.state == "hold")
            )
            res_held = await session.exec(stmt_held)
            # Holds are recorded as negative values (-amount)
            held_sum = abs(sum(res_held.all()))

            available = max(0, posted_sum - held_sum)
            balances[b.kind] = {
                "bucket_id": b.id,
                "name": b.name,
                "posted": posted_sum,
                "held": held_sum,
                "available": available
            }
        return balances

    @staticmethod
    async def can_spend(
        session: AsyncSession,
        user_id: UUID,
        amount_minor: int,
        source_kind: str,
        necessity: str,
        has_approved_override: bool = False
    ) -> Tuple[bool, str, str]:
        """
        Evaluate deterministic Trinity invariants against a proposed expenditure.
        
        Args:
            session: Active database AsyncSession.
            user_id: UUID of the user.
            amount_minor: Purchase amount in minor units (cents).
            source_kind: Target bucket ('daily', 'freedom', 'bank', etc.).
            necessity: Classified necessity category ('daily_living', 'freedom', 'bill', etc.).
            has_approved_override: Whether an Escape Window override was completed.
            
        Returns:
            Tuple of (is_allowed: bool, status: str, rationale: str)
            Status is one of: 'allowed', 'needs_override', 'denied'.
        """
        if amount_minor <= 0:
            return False, "denied", "Amount must be strictly positive."

        balances = await LedgerEngine.get_bucket_balances(session, user_id)
        source_info = balances.get(source_kind)
        if not source_info:
            return False, "denied", f"Bucket '{source_kind}' not found."

        # Rule 1: Vault is locked long-term savings
        if source_kind == "vault":
            return False, "denied", "Vault is locked long-term savings. Direct spend is strictly forbidden."

        # Rule 2: Bills bucket is strictly reserved
        if source_kind == "bills" and necessity != "bill":
            return False, "denied", "Bills bucket is strictly reserved for fixed contractual obligations."

        # Rule 3: Balance check
        if source_info["available"] < amount_minor:
            # Check fallback to Bank
            if source_kind in ("daily", "freedom"):
                return False, "needs_override", f"Insufficient funds in {source_kind}. Raiding Bank requires an Escape Window override."
            return False, "denied", "Insufficient available funds."

        # Rule 4: Bank direct spend protection
        if source_kind == "bank" and necessity != "bill":
            if not has_approved_override:
                return False, "needs_override", "Bank direct spend is locked to protect rent and daily living. Escape Window override required."

        # Rule 5: Discretionary / Hedonism protection
        if necessity == "freedom" and source_kind != "freedom":
            if not has_approved_override:
                return False, "needs_override", "Discretionary spend must come from Freedom envelope. Dipping into other buckets requires an override."

        return True, "allowed", "Spend satisfies Trinity policy."

    @staticmethod
    async def place_hold(
        session: AsyncSession,
        user_id: UUID,
        bucket_id: UUID,
        amount_minor: int,
        intent_id: UUID,
        paypal_order_id: Optional[str] = None
    ) -> LedgerEntry:
        """
        Place a debit hold on the bucket before initiating external PayPal checkout.
        Reserves the funds so subsequent requests cannot double-spend.
        
        Args:
            session: Active database AsyncSession.
            user_id: UUID of the user.
            bucket_id: UUID of the source bucket.
            amount_minor: Positive amount in cents.
            intent_id: Associated Intent UUID.
            paypal_order_id: Optional PayPal Order ID from Orders v2 API.
            
        Returns:
            LedgerEntry: The created hold ledger entry.
        """
        transfer_id = uuid4()
        idempotency_key = f"hold:{intent_id}"

        hold_entry = LedgerEntry(
            transfer_id=transfer_id,
            user_id=user_id,
            bucket_id=bucket_id,
            amount=-abs(amount_minor),  # Holds debit available balance
            currency="USD",
            state="hold",
            intent_id=intent_id,
            paypal_order_id=paypal_order_id,
            idempotency_key=idempotency_key,
            created_at=utc_now()
        )
        session.add(hold_entry)
        await session.commit()
        await session.refresh(hold_entry)
        return hold_entry

    @staticmethod
    async def settle_hold(
        session: AsyncSession,
        intent_id: UUID,
        paypal_capture_id: str
    ) -> Optional[LedgerEntry]:
        """
        Convert a pending hold into a settled posted debit upon receiving PayPal capture.
        
        Args:
            session: Active database AsyncSession.
            intent_id: Associated Intent UUID.
            paypal_capture_id: PayPal Capture ID from webhook or capture response.
            
        Returns:
            Optional[LedgerEntry]: Updated ledger entry if hold existed.
        """
        stmt = select(LedgerEntry).where(LedgerEntry.intent_id == intent_id).where(LedgerEntry.state == "hold")
        result = await session.exec(stmt)
        entry = result.first()
        if entry:
            entry.state = "posted"
            entry.paypal_capture_id = paypal_capture_id
            entry.posted_at = utc_now()
            session.add(entry)
            await session.commit()
            await session.refresh(entry)
        return entry

    @staticmethod
    async def release_hold(session: AsyncSession, intent_id: UUID) -> bool:
        """
        Release a hold if PayPal payment is canceled or fails.
        Restores available balance without altering historical transaction audit log.
        
        Args:
            session: Active database AsyncSession.
            intent_id: Associated Intent UUID.
            
        Returns:
            bool: True if hold was found and released.
        """
        stmt = select(LedgerEntry).where(LedgerEntry.intent_id == intent_id).where(LedgerEntry.state == "hold")
        result = await session.exec(stmt)
        entry = result.first()
        if entry:
            entry.state = "released"
            session.add(entry)
            await session.commit()
            return True
        return False

    @staticmethod
    async def record_double_entry_transfer(
        session: AsyncSession,
        user_id: UUID,
        from_bucket_id: UUID,
        to_bucket_id: UUID,
        amount_minor: int,
        entry_kind: str,
        memo: str,
        from_bucket_kind: Optional[str] = None,
        to_bucket_kind: Optional[str] = None,
        created_at: Optional[datetime] = None
    ) -> Tuple[LedgerEntry, LedgerEntry]:
        """
        Record a zero-sum double-entry transfer between two internal buckets.
        Creates balanced debit (-amount) and credit (+amount) legs sharing a single transfer_id.
        
        Args:
            session: Active database AsyncSession.
            user_id: UUID of the user.
            from_bucket_id: UUID of the source bucket (debited).
            to_bucket_id: UUID of the destination bucket (credited).
            amount_minor: Positive amount in cents to transfer.
            entry_kind: Categorization tag ('vault_skim', 'morning_topup', etc.).
            memo: Audit explanation string.
            from_bucket_kind: Optional kind tag for counterparty provenance.
            to_bucket_kind: Optional kind tag for counterparty provenance.
            created_at: Optional explicit timestamp (for seed data / historical backfills).
            
        Returns:
            Tuple[LedgerEntry, LedgerEntry]: (debit_leg, credit_leg) sharing transfer_id.
        """
        transfer_id = uuid4()
        ts = created_at or utc_now()
        amt = abs(amount_minor)

        debit_leg = LedgerEntry(
            transfer_id=transfer_id,
            user_id=user_id,
            bucket_id=from_bucket_id,
            amount=-amt,
            currency="USD",
            state="posted",
            entry_kind=entry_kind,
            counterparty_bucket=to_bucket_kind,
            memo=memo,
            idempotency_key=f"transfer:{transfer_id}:debit",
            created_at=ts,
            posted_at=ts
        )
        credit_leg = LedgerEntry(
            transfer_id=transfer_id,
            user_id=user_id,
            bucket_id=to_bucket_id,
            amount=amt,
            currency="USD",
            state="posted",
            entry_kind=entry_kind,
            counterparty_bucket=from_bucket_kind,
            memo=memo,
            idempotency_key=f"transfer:{transfer_id}:credit",
            created_at=ts,
            posted_at=ts
        )
        session.add(debit_leg)
        session.add(credit_leg)
        await session.commit()
        await session.refresh(debit_leg)
        await session.refresh(credit_leg)
        return debit_leg, credit_leg
