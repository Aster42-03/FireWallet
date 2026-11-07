from typing import Any, Dict, List
from uuid import UUID
from fastapi import APIRouter, Depends
from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.user import User
from app.models.coach import CoachThread, CoachMessage
from app.schemas.common import CoachMessageRequest, CoachMessageResponse
from app.api.v1.auth import get_current_user
from app.agents.insights.coach import handle_coach_query

router = APIRouter(prefix="/coach", tags=["Financial Coach"])

@router.post("/messages", response_model=CoachMessageResponse)
async def post_coach_message(
    body: CoachMessageRequest,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """Send conversational query to the Financial Coach (powered by Advanced Reasoning Model)."""
    return await handle_coach_query(
        session=session,
        user_id=user.id,
        utterance=body.utterance,
        thread_id=body.thread_id,
        chart_id=body.chart_id,
        filter_context=body.filter_context
    )

@router.get("/threads")
async def list_threads(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> List[Dict[str, Any]]:
    stmt = select(CoachThread).where(CoachThread.user_id == user.id).order_by(col(CoachThread.updated_at).desc())
    res = await session.exec(stmt)
    return [t.model_dump() for t in res.all()]

@router.get("/threads/{thread_id}/messages")
async def get_thread_messages(
    thread_id: UUID,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> List[Dict[str, Any]]:
    stmt = (
        select(CoachMessage)
        .where(CoachMessage.thread_id == thread_id)
        .order_by(col(CoachMessage.created_at).asc())
    )
    res = await session.exec(stmt)
    return [m.model_dump() for m in res.all()]
