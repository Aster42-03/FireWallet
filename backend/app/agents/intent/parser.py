"""
Financial Spend Intent Classifier & Parsing Gateway
===================================================
Single-call Natural Language Processing (NLP) gateway that intercepts prospective
user spending intents, distilling a concise 2-5 word `short_tag` (e.g., 'groceries',
'takeout', 'gift for family') and classifying category, necessity, recommended Trinity
bucket, and genuine emergency status prior to deterministic firewall evaluation.
"""

import json
import time
from typing import Any, Dict, Optional
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.agents.shared.llm_client import llm_client
from app.agents.rag import normalize_short_tag, is_genuine_emergency
from app.models.intent import AgentRun


async def parse_intent_utterance(
    session: AsyncSession,
    intent_id: UUID,
    utterance: str,
    amount_minor: int,
    merchant_name: str = "",
    balances_snapshot: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Parses a natural language spend intent into a structured classification payload
    in a single ultra-fast LLM call (Groq `llama-3.3-70b-versatile` -> `gpt-4o-mini` -> local fallback).
    """
    start_time = time.time()
    prompt = (
        f"You are Trinity's financial Intent Classifier. Analyze this spending intent:\n"
        f"Utterance: '{utterance}'\n"
        f"Amount: ${amount_minor / 100:.2f}\n"
        f"Merchant: '{merchant_name}'\n\n"
        f"Return strict JSON with keys:\n"
        f"- short_tag: concise 2-5 word lowercase summary phrase (e.g. 'groceries', 'takeout', 'gift for family', 'movie ticket')\n"
        f"- category: string (e.g. 'groceries', 'transit', 'eating_out', 'entertainment', 'utilities', 'gifts', 'emergency')\n"
        f"- necessity: one of ('bill', 'daily_living', 'freedom', 'ambiguous')\n"
        f"- recommended_bucket: one of ('bills', 'daily', 'freedom', 'bank', 'vault')\n"
        f"- is_emergency: boolean (true ONLY for genuine medical/ER/hospital/stranded/shutoff emergencies, NOT celebrations)\n"
        f"- confidence: float (0.0-1.0)\n"
        f"- rationale: one clear user-facing sentence\n"
        f"- flags: list of strings"
    )

    messages = [
        {"role": "system", "content": "You are a precise financial intent classifier. Output JSON only."},
        {"role": "user", "content": prompt},
    ]

    raw_response = await llm_client.chat_completion(messages, temperature=0.1, json_mode=True)
    latency_ms = int((time.time() - start_time) * 1000)

    try:
        parsed = json.loads(raw_response)
        if not isinstance(parsed, dict):
            raise ValueError("Expected JSON object")
    except Exception:
        parsed = {
            "category": "other",
            "necessity": "freedom",
            "recommended_bucket": "freedom",
            "confidence": 0.5,
            "rationale": "Discretionary spend defaults to Freedom envelope.",
            "flags": ["parse_fallback"],
        }

    # Deterministic post-processing guardrails on short_tag & emergency verification
    category = str(parsed.get("category") or "other")
    parsed["short_tag"] = normalize_short_tag(
        parsed.get("short_tag"),
        fallback_utterance=utterance,
        category=category,
        merchant_name=merchant_name,
    )
    det_emerg, emerg_reason = is_genuine_emergency(utterance, merchant_name, category)
    parsed["is_emergency"] = det_emerg
    if det_emerg and "valid_emergency" not in parsed.get("flags", []):
        parsed["flags"] = list(parsed.get("flags") or []) + ["valid_emergency"]
        parsed["rationale"] = parsed.get("rationale") or emerg_reason

    agent_run = AgentRun(
        kind="intent",
        intent_id=intent_id,
        model=llm_client.model,
        prompt_version="v3-rag-monolithic",
        latency_ms=latency_ms,
        raw_response=raw_response,
        parsed=json.dumps(parsed),
    )
    session.add(agent_run)
    await session.commit()

    return parsed
