import json
import time
from typing import Any, Dict
from uuid import UUID

from app.agents.shared.llm_client import llm_client
from app.models.intent import AgentRun
from sqlmodel.ext.asyncio.session import AsyncSession

async def parse_intent_utterance(
    session: AsyncSession,
    intent_id: UUID,
    utterance: str,
    amount_minor: int,
    merchant_name: str = "",
    balances_snapshot: Dict[str, Any] = None
) -> Dict[str, Any]:
    """Parse natural language intent into structured category, necessity, and recommended bucket."""
    start_time = time.time()
    prompt = (
        f"You are Trinity's financial Intent Classifier. Analyze this spending intent:\n"
        f"Utterance: '{utterance}'\n"
        f"Amount: ${amount_minor / 100:.2f}\n"
        f"Merchant: '{merchant_name}'\n\n"
        f"Return strict JSON with keys: category, necessity (bill, daily_living, freedom, ambiguous), "
        f"recommended_bucket (bills, daily, freedom, bank, none), confidence (0.0-1.0), "
        f"rationale (one clear user-facing sentence), and flags (list of strings)."
    )

    messages = [
        {"role": "system", "content": "You are a precise financial intent classifier. Output JSON only."},
        {"role": "user", "content": prompt}
    ]

    raw_response = await llm_client.chat_completion(messages, temperature=0.1, json_mode=True)
    latency_ms = int((time.time() - start_time) * 1000)

    try:
        parsed = json.loads(raw_response)
    except Exception:
        parsed = {
            "category": "other",
            "necessity": "freedom",
            "recommended_bucket": "freedom",
            "confidence": 0.5,
            "rationale": "Discretionary spend defaults to Freedom envelope.",
            "flags": ["parse_fallback"]
        }

    # Record audit log
    agent_run = AgentRun(
        kind="intent",
        intent_id=intent_id,
        model=llm_client.model,
        latency_ms=latency_ms,
        raw_response=raw_response,
        parsed=json.dumps(parsed)
    )
    session.add(agent_run)
    await session.commit()

    return parsed
