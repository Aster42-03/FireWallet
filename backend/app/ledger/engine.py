from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple
from uuid import UUID, uuid4
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.bucket import Bucket
from app.models.ledger import LedgerEntry
from app.models.user import BudgetPolicy

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

class LedgerEngine:
    @staticmethod
    async def get_bucket_balances(session: AsyncSession, user_id: UUID) -> Dict[str, Dict[str, int]]:
        """Calculate available, held, and total balances for each bucket."""
        statement = select(Bucket).where(Bucket.user_id == user_id)
        result = await session.exec(statement)
        buckets = result.all()

        balances = {}
        for b in buckets:
            # Query posted entries
            stmt_posted = (
                select(LedgerEntry.amount)
                .where(LedgerEntry.bucket_id == b.id)
                .where(LedgerEntry.state == "posted")
            )
            res_posted = await session.exec(stmt_posted)
            posted_sum = sum(res_posted.all())

            # Query active holds
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
        Evaluate deterministic Trinity invariants.
        Returns: (is_allowed, status, rationale)
        """
        if amount_minor <= 0:
            return False, "denied", "Amount must be strictly positive."

        balances = await LedgerEngine.get_bucket_balances(session, user_id)
        source_info = balances.get(source_kind)
        if not source_info:
            return False, "denied", f"Bucket '{source_kind}' not found."

        # Rule 1: Vault is locked
        if source_kind == "vault":
            return False, "denied", "Vault is locked long-term savings. Direct spend is strictly forbidden."

        # Rule 2: Bills bucket is reserved
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
        """Place a debit hold on the bucket before initiating PayPal execution."""
        transfer_id = uuid4()
        idempotency_key = f"hold:{intent_id}"

        hold_entry = LedgerEntry(
            transfer_id=transfer_id,
            user_id=user_id,
            bucket_id=bucket_id,
            amount=-abs(amount_minor),  # Holds debit available
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
        """Convert a hold into a settled posted debit upon receiving PayPal webhook capture."""
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
        """Release a hold if PayPal payment is canceled or fails."""
        stmt = select(LedgerEntry).where(LedgerEntry.intent_id == intent_id).where(LedgerEntry.state == "hold")
        result = await session.exec(stmt)
        entry = result.first()
        if entry:
            entry.state = "released"
            session.add(entry)
            await session.commit()
            return True
        return False
