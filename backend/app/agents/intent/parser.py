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
from typing import Any, Dict, Optional, Set
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.agents.shared.llm_client import llm_client
from app.agents.rag import normalize_short_tag, is_genuine_emergency
from app.models.intent import AgentRun


CANONICAL_CATEGORIES: Set[str] = {
    "groceries",
    "transit",
    "utilities",
    "entertainment",
    "gifts",
    "eating_out",
    "emergency",
}

CATEGORY_ALIASES: Dict[str, str] = {
    "dining_out": "eating_out",
    "dining out": "eating_out",
    "dining": "eating_out",
    "takeout": "eating_out",
    "take_out": "eating_out",
    "restaurant": "eating_out",
    "restaurants": "eating_out",
    "fast food": "eating_out",
    "fast_food": "eating_out",
    "food": "eating_out",
    "cafe": "eating_out",
    "coffee": "eating_out",
    "medical_emergency": "emergency",
    "savings_violation": "emergency",
    "medical": "emergency",
    "hospital": "emergency",
    "er": "emergency",
    "urgent care": "emergency",
    "urgent_care": "emergency",
    "grocery": "groceries",
    "supermarket": "groceries",
    "transport": "transit",
    "transportation": "transit",
    "subway": "transit",
    "bus": "transit",
    "utility": "utilities",
    "bills": "utilities",
    "bill": "utilities",
    "rent": "utilities",
    "housing": "utilities",
    "fun": "entertainment",
    "movies": "entertainment",
    "movie": "entertainment",
    "ticket": "entertainment",
    "tickets": "entertainment",
    "gift": "gifts",
    "presents": "gifts",
    "present": "gifts",
}


def normalize_category(
    raw_category: Optional[str],
    utterance: str = "",
    merchant_name: str = ""
) -> str:
    """
    Normalizes any raw or LLM-produced category string into the canonical core category set:
    `groceries`, `transit`, `utilities`, `entertainment`, `gifts`, `eating_out`, `emergency`.
    """
    if raw_category:
        cleaned = raw_category.strip().lower().replace("-", "_")
        if cleaned in CANONICAL_CATEGORIES:
            return cleaned
        if cleaned in CATEGORY_ALIASES:
            return CATEGORY_ALIASES[cleaned]
    # Fall back to deterministic heuristic classification
    heuristic = llm_client._classify_text_heuristically(utterance, merchant_name)
    h_cat = heuristic.get("category", "eating_out")
    if h_cat in CANONICAL_CATEGORIES:
        return h_cat
    if h_cat in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[h_cat]
    return "eating_out"


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
        f"- category: exactly one of ('groceries', 'transit', 'utilities', 'entertainment', 'gifts', 'eating_out', 'emergency')\n"
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
        parsed = llm_client._classify_text_heuristically(utterance, merchant_name)
        parsed["flags"] = list(parsed.get("flags") or []) + ["parse_fallback"]

    # Deterministic post-processing guardrails on category, short_tag & emergency verification
    det_emerg, emerg_reason = is_genuine_emergency(utterance, merchant_name, str(parsed.get("category") or ""))
    parsed["is_emergency"] = det_emerg

    if det_emerg:
        parsed["category"] = "emergency"
        if "valid_emergency" not in parsed.get("flags", []):
            parsed["flags"] = list(parsed.get("flags") or []) + ["valid_emergency"]
        if "zero_cooldown" not in parsed.get("flags", []):
            parsed["flags"] = list(parsed.get("flags") or []) + ["zero_cooldown"]
        parsed["rationale"] = parsed.get("rationale") or emerg_reason
    else:
        parsed["category"] = normalize_category(
            parsed.get("category"),
            utterance=utterance,
            merchant_name=merchant_name,
        )

    category = parsed["category"]
    parsed["short_tag"] = normalize_short_tag(
        parsed.get("short_tag"),
        fallback_utterance=utterance,
        category=category,
        merchant_name=merchant_name,
    )

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
