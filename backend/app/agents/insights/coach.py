import json
import re
from typing import Any, Dict, Optional
from uuid import UUID, uuid4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.agents.shared.llm_client import llm_client
from app.models.coach import CoachThread, CoachMessage
from app.ledger.engine import LedgerEngine
from app.analytics.summary import get_hud_summary
from app.analytics.deep_analytics import query_deep_ledger, detect_spending_anomalies

async def handle_coach_query(
    session: AsyncSession,
    user_id: UUID,
    utterance: str,
    thread_id: Optional[UUID] = None,
    chart_id: Optional[str] = None,
    filter_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Financial Coach reasoning engine.
    Supports chart literacy, affordability simulation, and AG Grid deep ledger analysis.
    """
    # Ensure thread exists
    if not thread_id:
        thread = CoachThread(user_id=user_id, title=utterance[:40])
        session.add(thread)
        await session.commit()
        await session.refresh(thread)
        thread_id = thread.id

    # Record user message
    user_msg = CoachMessage(
        thread_id=thread_id,
        role="user",
        content=utterance,
        chart_id=chart_id
    )
    session.add(user_msg)
    await session.commit()

    # Gather data context
    balances = await LedgerEngine.get_bucket_balances(session, user_id)
    hud_data = await get_hud_summary(session, user_id)

    citations: Dict[str, Any] = {"buckets": []}
    suggest_intent: Optional[Dict[str, Any]] = None

    # Check for prospective spend / affordability
    spend_match = re.search(r"\$?(\d+(?:\.\d{2})?)", utterance)
    detected_amount_cents = int(float(spend_match.group(1)) * 100) if spend_match else None

    # Check context mode
    if filter_context:
        # AG Grid Deep Analytics Mode
        deep_res = await query_deep_ledger(
            session=session,
            user_id=user_id,
            category=filter_context.get("category"),
            bucket=filter_context.get("bucket"),
            limit=25
        )
        anomalies = await detect_spending_anomalies(session=session, user_id=user_id)
        context_str = (
            f"AG Grid Active Filter Context:\n"
            f"- Filter: {filter_context}\n"
            f"- Filtered Count: {deep_res['total_count']} transactions\n"
            f"- Filtered Debits: ${deep_res['aggregates']['total_debits'] / 100:.2f}\n"
            f"- Detected Anomalies: {anomalies[:3]}\n"
        )
        citations["deep_ledger"] = {"filtered_count": deep_res["total_count"]}
    elif chart_id:
        # Chart Literacy Mode
        chart_obj = next((c for c in hud_data["charts"] if c["id"] == chart_id), None)
        context_str = f"User is asking about HUD Chart '{chart_id}':\n{json.dumps(chart_obj)}"
        citations["chart_id"] = chart_id
    else:
        # Standard Coaching Mode
        context_str = (
            f"Current Balances:\n"
            f"- Bank (Locked): ${balances.get('bank', {}).get('available', 0) / 100:.2f}\n"
            f"- Daily Allowance: ${balances.get('daily', {}).get('available', 0) / 100:.2f}\n"
            f"- Freedom (Fun Money): ${balances.get('freedom', {}).get('available', 0) / 100:.2f}\n"
            f"- Vault (Savings): ${balances.get('vault', {}).get('available', 0) / 100:.2f}\n"
            f"- Bills (Reserved): ${balances.get('bills', {}).get('available', 0) / 100:.2f}\n"
        )
        citations["buckets"] = ["daily", "freedom"]

    system_prompt = (
        "You are FireWallet's Financial Coach. You are calm, plain-spoken, supportive, and analytical. "
        "Your focus is helping students and irregular earners build financial literacy. "
        "Explain things simply without financial jargon or moralizing shame. "
        "Strict rule: You cannot execute transactions or modify balances. If a user wants to spend, explain whether it fits "
        "and tell them they can log it in Quick Intent."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context:\n{context_str}\n\nUser Question:\n{utterance}"}
    ]

    reply = await llm_client.chat_completion(messages, temperature=0.3)

    # Attach suggest_intent if user asks about a purchase
    if detected_amount_cents and ("afford" in utterance.lower() or "buy" in utterance.lower() or "ticket" in utterance.lower() or "eat" in utterance.lower()):
        freedom_avail = balances.get("freedom", {}).get("available", 0)
        daily_avail = balances.get("daily", {}).get("available", 0)

        target_bucket = "freedom" if "movie" in utterance.lower() or "game" in utterance.lower() or "takeout" in utterance.lower() else "daily"
        suggest_intent = {
            "utterance": utterance[:60],
            "amount": detected_amount_cents,
            "category": "entertainment" if target_bucket == "freedom" else "groceries",
            "target_bucket": target_bucket
        }

    # Record assistant message
    asst_msg = CoachMessage(
        thread_id=thread_id,
        role="assistant",
        content=reply,
        citations_json=json.dumps(citations),
        suggest_intent_json=json.dumps(suggest_intent) if suggest_intent else None
    )
    session.add(asst_msg)
    await session.commit()
    await session.refresh(asst_msg)

    return {
        "thread_id": thread_id,
        "message_id": asst_msg.id,
        "reply": reply,
        "citations": citations,
        "suggest_intent": suggest_intent
    }
