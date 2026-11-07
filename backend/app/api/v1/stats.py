from typing import Any, Dict
from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.database import get_session
from app.models.user import User
from app.api.v1.auth import get_current_user
from app.analytics.summary import get_hud_summary

router = APIRouter(prefix="/stats", tags=["HUD Analytics"])

@router.get("/summary")
async def get_summary(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session)
) -> Dict[str, Any]:
    """Retrieve HUD chart metrics, category spend, and rollover series."""
    return await get_hud_summary(session, user.id)
