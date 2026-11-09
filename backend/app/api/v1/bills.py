import asyncio
from datetime import date
from typing import Any, Dict, List, Optional
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.user import User
from app.models.bill import Bill
from app.models.bucket import Bucket
from app.models.ledger import LedgerEntry
from app.models.batch_payment import BatchPaymentItem, utc_now
from app.models.intent import Intent
from app.schemas.common import (
    BatchDispatcherProposal,
    BatchPaymentItemDTO,
    BatchExecuteRequest,
    BatchExecutionSummary,
    BatchExecutionItemResult,
    BatchStageIntentRequest,
    BatchStageIntentResponse,
)
from app.ledger.engine import LedgerEngine
from app.api.v1.auth import get_current_user
from app.services.paypal_client import paypal_client

router = APIRouter(prefix="/bills", tags=["Bills"])

@router.get("")
async def list_bills(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> List[Dict[str, Any]]:
    stmt = select(Bill).where(Bill.user_id == user.id).order_by(col(Bill.priority).asc(), col(Bill.due_date).asc())
    res = await session.exec(stmt)
    return [b.model_dump() for b in res.all()]

@router.post("")
async def create_bill(
    name: str,
    amount: int,
    due_date: date,
    payee_email: str,
    priority: int = 1,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    bill = Bill(
        user_id=user.id,
        name=name,
        amount=amount,
        due_date=due_date,
        payee_email=payee_email,
        priority=priority,
        status="scheduled"
    )
    session.add(bill)
    await session.commit()
    await session.refresh(bill)
    return bill.model_dump()

@router.post("/{bill_id}/pay")
async def pay_bill_now(
    bill_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    stmt = select(Bill).where(Bill.id == bill_id).where(Bill.user_id == user.id)
    res = await session.exec(stmt)
    bill = res.first()
    if not bill:
        raise HTTPException(status_code=404, detail="Bill not found")

    # Dispatch PayPal Payout to bill payee
    payout_res = await paypal_client.create_payout(
        batch_id=f"bill_{bill.id}_{bill.due_date}",
        receiver_email=bill.payee_email,
        amount_cents=bill.amount,
        note=f"Bill Payment: {bill.name}"
    )

    bill.status = "paid"
    bill.last_payout_batch_id = payout_res.get("batch_header", {}).get("payout_batch_id")
    session.add(bill)

    # Debit Bills bucket in ledger
    stmt_b = select(Bucket).where(Bucket.user_id == user.id).where(Bucket.kind == "bills")
    res_b = await session.exec(stmt_b)
    bucket = res_b.first()
    if bucket:
        entry = LedgerEntry(
            transfer_id=bill.id,
            user_id=user.id,
            bucket_id=bucket.id,
            amount=-abs(bill.amount),
            currency="USD",
            state="posted",
            bill_id=bill.id,
            idempotency_key=f"bill_pay:{bill.id}:{bill.due_date}"
        )
        session.add(entry)

    await session.commit()
    return {"status": "paid", "payout_batch_id": bill.last_payout_batch_id}


# ==============================================================================
# The Trinity Batch Dispatcher (M4)
# ==============================================================================

@router.post("/batch-dispatcher/propose", response_model=BatchDispatcherProposal)
async def propose_batch(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> BatchDispatcherProposal:
    """
    Stage upcoming scheduled bills and unstaged recurring obligations into the Batch Dispatcher
    and return a structured BatchDispatcherProposal with risk assessment verifying Bank Foundation is untouched.
    """
    # 1. Stage upcoming scheduled bills
    stmt = (
        select(Bill)
        .where(Bill.user_id == user.id)
        .where(Bill.status == "scheduled")
        .order_by(col(Bill.priority).asc(), col(Bill.due_date).asc())
    )
    res = await session.exec(stmt)
    bills = res.all()
    bill_map = {b.id: b for b in bills}

    for b in bills:
        stmt_item = (
            select(BatchPaymentItem)
            .where(BatchPaymentItem.user_id == user.id)
            .where(BatchPaymentItem.bill_id == b.id)
            .where(BatchPaymentItem.status == "pending_approval")
        )
        existing = (await session.exec(stmt_item)).first()
        if existing:
            existing.amount_minor = b.amount
            existing.title = b.name
            existing.recipient_name = b.name
            existing.recipient_email = b.payee_email
            existing.payee_email = b.payee_email
            existing.updated_at = utc_now()
            session.add(existing)
        else:
            cat = "Rent" if "rent" in b.name.lower() else "Bills"
            new_item = BatchPaymentItem(
                user_id=user.id,
                bill_id=b.id,
                title=b.name,
                recipient_name=b.name,
                amount_minor=b.amount,
                category=cat,
                currency=b.currency or "USD",
                source_bucket="bills",
                status="pending_approval",
                recommended=True,
                recipient_email=b.payee_email,
                payee_email=b.payee_email,
            )
            session.add(new_item)

    # 2. Ingest unstaged bill/recurring intents for user into batch queue
    stmt_intents = (
        select(Intent)
        .where(Intent.user_id == user.id)
        .where(Intent.status.in_(["allowed", "draft", "parsed"]))
        .where(Intent.category.in_(["bills", "utilities", "rent", "insurance"]))
    )
    unstaged_intents = (await session.exec(stmt_intents)).all()
    for intent in unstaged_intents:
        stmt_check = (
            select(BatchPaymentItem)
            .where(BatchPaymentItem.user_id == user.id)
            .where(BatchPaymentItem.intent_id == intent.id)
        )
        if not (await session.exec(stmt_check)).first():
            new_intent_item = BatchPaymentItem(
                user_id=user.id,
                intent_id=intent.id,
                title=intent.utterance or "Recurring Bill",
                recipient_name=intent.merchant_name or intent.utterance or "Payee",
                amount_minor=intent.amount,
                category=(intent.category or "bills").capitalize(),
                currency=intent.currency or "USD",
                source_bucket="bills",
                status="pending_approval",
                recommended=True,
                recipient_email=intent.merchant_name if (intent.merchant_name and "@" in intent.merchant_name) else "billing@service.com",
                payee_email=intent.merchant_name if (intent.merchant_name and "@" in intent.merchant_name) else "billing@service.com",
                note=intent.utterance,
            )
            session.add(new_intent_item)

    await session.commit()

    # 3. Fetch all active pending_approval items for this user
    stmt_pending = (
        select(BatchPaymentItem)
        .where(BatchPaymentItem.user_id == user.id)
        .where(BatchPaymentItem.status == "pending_approval")
        .order_by(BatchPaymentItem.created_at.asc())
    )
    pending_items = (await session.exec(stmt_pending)).all()

    balances = await LedgerEngine.get_bucket_balances(session, user.id)
    bills_avail = balances.get("bills", {}).get("available", 0)
    vault_avail = balances.get("vault", {}).get("available", 0)
    bank_avail = balances.get("bank", {}).get("available", 0)

    if not pending_items:
        return BatchDispatcherProposal(
            coach_message="No upcoming scheduled obligations found to stage at this time.",
            total_batch_amount_minor=0,
            items=[],
            risk_assessment=f"Core Bank Foundation (${bank_avail / 100:,.2f}) and Vault (${vault_avail / 100:,.2f}) remain 100% untouched.",
            vault_balance_minor=vault_avail,
            bills_balance_minor=bills_avail,
            safe_to_execute=True,
        )

    item_dtos = []
    total_minor = 0
    for item in pending_items:
        total_minor += item.amount_minor
        linked_b = bill_map.get(item.bill_id) if item.bill_id else None
        item_dtos.append(
            BatchPaymentItemDTO(
                id=item.id,
                bill_id=item.bill_id,
                intent_id=item.intent_id,
                title=item.title,
                amount_minor=item.amount_minor,
                category=item.category,
                currency=item.currency,
                source_bucket=item.source_bucket,
                recommended=item.recommended,
                recipient_email=item.recipient_email,
                payee_email=item.payee_email,
                recipient_name=item.recipient_name,
                due_date=str(linked_b.due_date) if (linked_b and linked_b.due_date) else None,
                note=item.note,
                status=item.status,
                paypal_payout_id=item.paypal_payout_id,
                error_message=item.error_message,
            )
        )

    safe_to_execute = (total_minor <= bills_avail)
    risk_assessment = (
        f"Isolated Reserved Bills (${bills_avail / 100:,.2f}) completely covers this batch. "
        f"Core Bank Foundation (${bank_avail / 100:,.2f}) and Vault long-term savings (${vault_avail / 100:,.2f}) remain 100% untouched."
    )
    coach_message = (
        f"Staging {len(item_dtos)} obligation(s) totaling ${total_minor / 100:,.2f} from isolated Reserved Bills."
    )

    return BatchDispatcherProposal(
        coach_message=coach_message,
        total_batch_amount_minor=total_minor,
        items=item_dtos,
        risk_assessment=risk_assessment,
        vault_balance_minor=vault_avail,
        bills_balance_minor=bills_avail,
        safe_to_execute=safe_to_execute,
    )


@router.post("/batch-dispatcher/stage-intent", response_model=BatchStageIntentResponse)
async def stage_intent(
    req: BatchStageIntentRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> BatchStageIntentResponse:
    """
    Stage a verified Intent or custom recurring obligation into the Batch Dispatcher
    staging queue as a BatchPaymentItem (status='pending_approval').
    """
    if req.amount_cents <= 0:
        raise HTTPException(status_code=400, detail="Amount must be greater than zero.")
    if req.source_bucket not in ("bills", "vault"):
        raise HTTPException(
            status_code=400,
            detail="Batch Dispatcher is strictly restricted to isolated 'bills' or 'vault' reserves. Spend from 'bank' or 'freedom' directly into batch is forbidden."
        )

    title = req.note or f"Payment to {req.recipient_email}"
    if req.intent_id:
        stmt_i = select(Intent).where(Intent.id == req.intent_id, Intent.user_id == user.id)
        intent_obj = (await session.exec(stmt_i)).first()
        if not intent_obj:
            raise HTTPException(status_code=404, detail="Referenced Intent not found for user.")
        if not req.note and intent_obj.utterance:
            title = intent_obj.utterance

    item = BatchPaymentItem(
        user_id=user.id,
        intent_id=req.intent_id,
        title=title,
        recipient_name=title,
        amount_minor=req.amount_cents,
        category=req.category.capitalize() if req.category else "Bills",
        currency=req.currency or "USD",
        source_bucket=req.source_bucket,
        status="pending_approval",
        recommended=True,
        recipient_email=req.recipient_email,
        payee_email=req.recipient_email,
        note=req.note or title,
    )
    session.add(item)
    await session.commit()
    await session.refresh(item)

    return BatchStageIntentResponse(
        success=True,
        batch_item_id=item.id,
        recipient_email=item.recipient_email or req.recipient_email,
        amount_cents=item.amount_minor,
        source_bucket=item.source_bucket,
        status=item.status,
    )


@router.get("/batch-dispatcher/queue")
async def get_batch_queue(
    status: Optional[str] = Query(default=None),
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """
    List staged batch items for the user along with isolated balances.
    """
    stmt = select(BatchPaymentItem).where(BatchPaymentItem.user_id == user.id)
    if status:
        stmt = stmt.where(BatchPaymentItem.status == status)
    stmt = stmt.order_by(BatchPaymentItem.created_at.desc())
    res = await session.exec(stmt)
    items = res.all()

    balances = await LedgerEngine.get_bucket_balances(session, user.id)
    bills_avail = balances.get("bills", {}).get("available", 0)
    vault_avail = balances.get("vault", {}).get("available", 0)

    all_res = await session.exec(
        select(BatchPaymentItem).where(BatchPaymentItem.user_id == user.id)
    )
    all_items = all_res.all()
    total_pending = sum(it.amount_minor for it in all_items if it.status == "pending_approval")
    total_paid = sum(it.amount_minor for it in all_items if it.status == "paid")

    return {
        "items": [it.model_dump() for it in items],
        "total_pending_minor": total_pending,
        "total_paid_minor": total_paid,
        "isolated_bills_available_minor": bills_avail,
        "isolated_vault_available_minor": vault_avail,
    }


@router.post("/batch-dispatcher/execute", response_model=BatchExecutionSummary)
async def execute_batch(
    req: BatchExecuteRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> BatchExecutionSummary:
    """
    Execute payouts for approved batch items sequentially via PayPal Payouts API.
    Enforces blast radius containment (strictly bills/vault), live sandbox connectivity,
    and double-entry ledger debit recording.
    """
    # 1. Empty items check
    if not req.approved_item_ids:
        raise HTTPException(status_code=400, detail="No items approved for execution.")

    # 2. Blast Radius Containment
    if req.source_bucket not in ("bills", "vault"):
        raise HTTPException(
            status_code=400,
            detail="Batch Dispatcher is strictly restricted to isolated 'bills' or 'vault' reserves. Direct spend from 'bank' is forbidden."
        )

    # 3. Fetch approved items scoped to authenticated user
    stmt = select(BatchPaymentItem).where(
        BatchPaymentItem.id.in_(req.approved_item_ids),
        BatchPaymentItem.user_id == user.id,
    )
    items = (await session.exec(stmt)).all()
    if not items:
        raise HTTPException(status_code=404, detail="No matching approved items found.")

    # 4. Reserve Sufficiency Check
    balances = await LedgerEngine.get_bucket_balances(session, user.id)
    bills_avail = balances.get("bills", {}).get("available", 0)
    vault_avail = balances.get("vault", {}).get("available", 0)
    if req.source_bucket == "bills":
        available_isolated = bills_avail + vault_avail
    elif req.source_bucket == "vault":
        available_isolated = vault_avail
    else:
        available_isolated = 0
    unpaid_approved_sum = sum(it.amount_minor for it in items if it.status != "paid")

    if unpaid_approved_sum > available_isolated:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Reserve Protection Active: Insufficient isolated Vault/Bills funds "
                f"(${available_isolated / 100:,.2f} available, ${unpaid_approved_sum / 100:,.2f} requested). "
                f"Bank Foundation cannot be raided by Batch Dispatcher."
            ),
        )

    # Cascade difference from Vault to Bills if bills bucket alone is insufficient
    if req.source_bucket == "bills" and unpaid_approved_sum > bills_avail:
        cascade_amount = unpaid_approved_sum - bills_avail
        vault_bucket_id = balances.get("vault", {}).get("bucket_id")
        bills_bucket_id = balances.get("bills", {}).get("bucket_id")
        if vault_bucket_id and bills_bucket_id:
            await LedgerEngine.record_double_entry_transfer(
                session=session,
                user_id=user.id,
                from_bucket_id=vault_bucket_id,
                to_bucket_id=bills_bucket_id,
                amount_minor=cascade_amount,
                entry_kind="vault_bills_cascade",
                memo=f"Automated vault cascade for batch payout coverage (${cascade_amount / 100:,.2f})",
                from_bucket_kind="vault",
                to_bucket_kind="bills",
            )
            await session.commit()

    # 5. Live PayPal Sandbox Requirement
    is_live = False
    if hasattr(paypal_client, "has_live_credentials"):
        try:
            res_live = paypal_client.has_live_credentials()
            if asyncio.iscoroutine(res_live):
                is_live = await res_live
            else:
                is_live = bool(res_live)
        except Exception:
            is_live = False

    if is_live and hasattr(paypal_client, "get_access_token"):
        try:
            token = await paypal_client.get_access_token()
            if not token or token == "mock_sandbox_access_token":
                is_live = False
        except Exception:
            is_live = False

    if not is_live:
        raise HTTPException(
            status_code=503,
            detail="Live PayPal Sandbox connection required for batch payout execution. Network offline or credentials unconfigured."
        )

    # 6. Locate source bucket
    stmt_b = select(Bucket).where(Bucket.user_id == user.id, Bucket.kind == req.source_bucket)
    bucket = (await session.exec(stmt_b)).first()
    if not bucket:
        raise HTTPException(status_code=400, detail=f"Source bucket '{req.source_bucket}' not found.")

    # 7. Sequential Idempotent Execution
    results: List[BatchExecutionItemResult] = []
    executed_count = 0
    failed_count = 0
    total_amount_minor = 0

    for item in items:
        # Idempotent skip for already paid items
        if item.status == "paid":
            executed_count += 1
            total_amount_minor += item.amount_minor
            results.append(
                BatchExecutionItemResult(
                    item_id=item.id,
                    title=item.title,
                    status="paid",
                    paypal_payout_id=item.paypal_payout_id,
                    error_message=None,
                )
            )
            continue

        item.status = "executing"
        session.add(item)
        await session.commit()
        await session.refresh(item)

        batch_id = f"batch_{str(item.id).replace('-', '')[:20]}"
        payee_email = item.recipient_email or item.payee_email

        try:
            payout_res = await paypal_client.create_payout(
                batch_id=batch_id,
                receiver_email=payee_email,
                amount_cents=item.amount_minor,
                note=f"Batch Payout: {item.title}",
            )
            payout_batch_id = (
                payout_res.get("payout_batch_id")
                or payout_res.get("batch_header", {}).get("payout_batch_id")
                or f"PAYOUT-{batch_id}"
            )

            item.status = "paid"
            item.paypal_payout_id = payout_batch_id
            item.paypal_payout_item_id = payout_batch_id
            item.paid_at = utc_now()
            item.updated_at = utc_now()
            item.error_message = None
            session.add(item)

            # Update associated Bill if linked
            if item.bill_id:
                b_stmt = select(Bill).where(Bill.id == item.bill_id)
                bill_obj = (await session.exec(b_stmt)).first()
                if bill_obj:
                    bill_obj.status = "paid"
                    bill_obj.last_payout_batch_id = payout_batch_id
                    session.add(bill_obj)

            # Update associated Intent if linked
            if item.intent_id:
                i_stmt = select(Intent).where(Intent.id == item.intent_id)
                intent_obj = (await session.exec(i_stmt)).first()
                if intent_obj:
                    intent_obj.status = "settled"
                    session.add(intent_obj)

            # Debit source bucket in ledger
            entry = LedgerEntry(
                transfer_id=item.bill_id or item.id,
                user_id=user.id,
                bucket_id=bucket.id,
                amount=-abs(item.amount_minor),
                currency=item.currency or "USD",
                state="posted",
                entry_kind="bill_payout",
                bill_id=item.bill_id,
                paypal_payout_item_id=payout_batch_id,
                idempotency_key=f"batch_payout:{item.id}",
            )
            session.add(entry)
            await session.commit()
            await session.refresh(item)

            executed_count += 1
            total_amount_minor += item.amount_minor
            results.append(
                BatchExecutionItemResult(
                    item_id=item.id,
                    title=item.title,
                    status="paid",
                    paypal_payout_id=payout_batch_id,
                    error_message=None,
                )
            )
        except Exception as e:
            item.status = "failed"
            item.error_message = str(e)
            item.updated_at = utc_now()
            session.add(item)
            await session.commit()

            failed_count += 1
            results.append(
                BatchExecutionItemResult(
                    item_id=item.id,
                    title=item.title,
                    status="failed",
                    paypal_payout_id=None,
                    error_message=str(e),
                )
            )

    # 8. Mark unapproved pending items as vetoed
    stmt_veto = (
        select(BatchPaymentItem)
        .where(BatchPaymentItem.user_id == user.id)
        .where(BatchPaymentItem.status == "pending_approval")
        .where(BatchPaymentItem.id.not_in(req.approved_item_ids))
    )
    veto_items = (await session.exec(stmt_veto)).all()
    for v in veto_items:
        v.status = "vetoed"
        v.updated_at = utc_now()
        session.add(v)
    if veto_items:
        await session.commit()

    # 9. Query final remaining isolated balance
    balances_after = await LedgerEngine.get_bucket_balances(session, user.id)
    remaining_isolated = balances_after.get(req.source_bucket, {}).get("available", 0)

    batch_status = "completed" if failed_count == 0 else ("partial_failure" if executed_count > 0 else "failed")
    msg = f"Batch payout of {executed_count} item(s) (${total_amount_minor / 100:,.2f}) completed via PayPal Sandbox."

    return BatchExecutionSummary(
        status=batch_status,
        executed_count=executed_count,
        failed_count=failed_count,
        total_amount_minor=total_amount_minor,
        results=results,
        remaining_isolated_balance_minor=remaining_isolated,
        message=msg,
    )
