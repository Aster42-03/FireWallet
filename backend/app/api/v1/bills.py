from datetime import date
from typing import Any, Dict, List
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.user import User
from app.models.bill import Bill
from app.models.bucket import Bucket
from app.models.ledger import LedgerEntry
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
