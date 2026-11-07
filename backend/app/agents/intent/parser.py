"""
Financial Spend Intent Classifier & Parsing Gateway
===================================================
Natural Language Processing (NLP) agent that intercepts prospective user spending
intents, classifying them into structured categories, necessity buckets, and policy rationale
prior to evaluating Trinity firewall rules or calling PayPal payment APIs.

Key Responsibilities:
1. Ingests natural language spend descriptions (e.g. "Trader Joe's groceries $24").
2. Maps utterance into category, necessity ('bill', 'daily_living', 'freedom'), and recommended bucket.
3. Audits full model latency and raw token responses in the AgentRun database table.
"""

import json
import time
from typing import Any, Dict, Optional
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
    balances_snapshot: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Parses a natural language spend intent into a structured classification payload.
    
    Args:
        session: Active AsyncSession for recording the AgentRun audit log.
        intent_id: UUID of the parent Intent record.
        utterance: User's raw natural language description.
        amount_minor: Proposed transaction amount in minor units (cents).
        merchant_name: Optional merchant name.
        balances_snapshot: Optional snapshot of current available bucket balances.
        
    Returns:
        Dict with keys:
            category: str (e.g. 'groceries', 'transit', 'entertainment')
            necessity: str ('bill', 'daily_living', 'freedom', 'ambiguous')
            recommended_bucket: str ('bills', 'daily', 'freedom', 'bank', 'none')
            confidence: float (0.0 to 1.0)
            rationale: str (User-facing explanation sentence)
            flags: List[str]
    """
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

    # Query LLM in strict JSON output mode
    raw_response = await llm_client.chat_completion(messages, temperature=0.1, json_mode=True)
    latency_ms = int((time.time() - start_time) * 1000)

    try:
        parsed = json.loads(raw_response)
    except Exception:
        # Graceful fallback if model output fails JSON parsing
        parsed = {
            "category": "other",
            "necessity": "freedom",
            "recommended_bucket": "freedom",
            "confidence": 0.5,
            "rationale": "Discretionary spend defaults to Freedom envelope.",
            "flags": ["parse_fallback"]
        }

    # Record full diagnostic audit trail in agent_runs table
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
