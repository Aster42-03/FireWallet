"""
Short-Tag Distillation, Emergency Verification & RAG Memory Engine
==================================================================
Provides deterministic and NLP utilities for:
1. Distilling natural language spend utterances & Coach prompts into concise 2-5 word
   summary tags (`short_tag`, e.g., 'groceries', 'takeout', 'gift for family', 'movie ticket')
   persisted in SQLite/PostgreSQL for both human review and Coach RAG retrieval.
2. Verifying genuine life/medical/safety emergencies (granting 0-second zero-delay override)
   vs. discretionary splurges (preserving the 200-char confession + 180s cooldown).
3. Retrieving lightweight Retrieval-Augmented Generation (RAG) memory context across historical
   Intents, Overrides, and Coach conversations.
"""

import re
from typing import Any, Dict, List, Optional, Set, Tuple
from uuid import UUID

from sqlmodel import select, col
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.intent import Intent, Override
from app.models.coach import CoachThread, CoachMessage
from app.models.bucket import Bucket

# Number word mapping for amounts expressed in words
_DOLLAR_WORDS: Dict[str, int] = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    "thirteen": 13, "fourteen": 14, "fifteen": 15, "sixteen": 16, "seventeen": 17,
    "eighteen": 18, "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40,
    "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90,
    "hundred": 100, "thousand": 1000
}

def parse_amount_cents_from_text(text: str) -> Optional[int]:
    """
    Parses money amounts in cents from text supporting:
    - Dollar symbols: '$15', '$24.50'
    - Numbers with currency words: '15 dollars', '25 bucks', '100 usd', '50 cents'
    - Word numbers: 'fifteen dollars', 'twenty bucks', 'five dollars'
    """
    if not text:
        return None
    raw = text.strip()
    lower = raw.lower()

    # 1. Direct $XX.XX or $XX
    m1 = re.search(r"\$(\d+(?:\.\d{1,2})?)", raw)
    if m1:
        return int(round(float(m1.group(1)) * 100))

    # 2. Number + dollar/dollars/bucks/cents/usd
    m2 = re.search(r"\b(\d+(?:\.\d{1,2})?)\s*(?:dollars?|bucks?|usd)\b", lower)
    if m2:
        return int(round(float(m2.group(1)) * 100))

    m2_cents = re.search(r"\b(\d+)\s*(?:cents?)\b", lower)
    if m2_cents:
        return int(m2_cents.group(1))

    # 3. Word numbers + dollar/dollars/bucks/usd/cents
    m3 = re.search(r"\b([a-z\s-]+)\s*(?:(dollars?|bucks?|usd)|(cents?))\b", lower)
    if m3:
        words = m3.group(1).replace("-", " ").split()
        is_cents = bool(m3.group(3))
        total = 0
        current = 0
        matched_any = False
        for w in words:
            if w in _DOLLAR_WORDS:
                matched_any = True
                val = _DOLLAR_WORDS[w]
                if val == 100:
                    current = (current if current > 0 else 1) * 100
                elif val == 1000:
                    current = (current if current > 0 else 1) * 1000
                    total += current
                    current = 0
                else:
                    current += val
            else:
                if current > 0:
                    total += current
                    current = 0
        total += current
        if matched_any and total > 0:
            return total if is_cents else total * 100

    return None

# Stop-words stripped only from leading/trailing filler when distilling tags
_FILLER_WORDS: Set[str] = {
    "can", "could", "should", "would", "i", "we", "me", "my", "afford", "to",
    "buy", "buying", "purchase", "purchasing", "pay", "paying", "spend", "spending",
    "get", "getting", "want", "need", "please", "today", "tonight", "now", "right",
    "a", "an", "the", "some", "this", "that", "from", "at", "in", "with", "is", "it",
    "let", "check", "if", "about", "around"
}

# Explicit splurge / celebration terms that disqualify emergency zero-cooldown bypass
_NON_EMERGENCY_LUXURY_TERMS: Tuple[str, ...] = (
    "steakhouse",
    "prime steak",
    "celebrating",
    "celebration",
    "promotion",
    "fancy dinner",
    "luxury",
    "designer",
    "concert",
    "nightclub",
    "bar tab",
    "video game",
    "gaming console",
    "ps5",
    "vacation",
)

# Genuine medical, safety, stranded, or critical shelter emergency indicators
_GENUINE_EMERGENCY_PATTERNS: Tuple[Tuple[str, str], ...] = (
    (r"\b(er|e\.r\.|emergency room)\b", "Emergency room medical care verified."),
    (r"\b(hospital|ambulance|urgent care|paramedic)\b", "Urgent hospital/medical care verified."),
    (r"\b(medical emergency|dental emergency|broken tooth|fracture|injury|stitches|surgery|x-ray|xray)\b", "Acute medical/injury treatment verified."),
    (r"\b(insulin|epipen|antibiotic|inhaler|urgent prescription|pharmacy copay|medical copay)\b", "Critical medication/pharmacy need verified."),
    (r"\b(stranded|car broke down|car breakdown|flat tire|tow truck|towing|roadside)\b", "Roadside/stranded safety emergency verified."),
    (r"\b(locked out|locksmith|unsafe|evacuation|shelter)\b", "Personal safety/shelter emergency verified."),
    (r"\b(power shutoff|water shutoff|utility shutoff|heat shutoff|gas shutoff|burst pipe|flooding|eviction)\b", "Critical utility/housing emergency verified."),
    (r"\b(family emergency|life emergency)\b", "Genuine family/life emergency verified."),
)


def is_genuine_emergency(
    text: str,
    merchant_name: str = "",
    category: str = ""
) -> Tuple[bool, str]:
    """
    Determines whether a spend utterance or override explanation represents a
    valid life, medical, safety, or critical infrastructure emergency.

    Crucially ignores false-positive phrases like 'from my emergency reserves'
    or 'emergency fund' when used to justify luxury/celebration spending.

    Returns:
        Tuple[bool, str]: (is_emergency, verification_reason)
    """
    combined = f"{text} {merchant_name} {category}".lower()

    # Neutralize phrases referring to the user's savings bucket rather than an event
    sanitized = re.sub(
        r"\bemergency\s+(reserves?|funds?|savings?|stash|account|bucket|money)\b",
        "reserve_account",
        combined,
    )

    # Check if explicit luxury/celebration splurge indicators are present
    has_luxury_signal = any(term in sanitized for term in _NON_EMERGENCY_LUXURY_TERMS)

    for pattern, reason in _GENUINE_EMERGENCY_PATTERNS:
        if re.search(pattern, sanitized):
            # Even if someone says "celebrating", an ambulance/hospital is medical;
            # otherwise guard against "promotion at steakhouse" false matches.
            if not has_luxury_signal or "hospital" in sanitized or "ambulance" in sanitized:
                return True, reason

    # Catch standalone "valid emergency" / "medical" / "clinic" if no luxury splurge terms
    if not has_luxury_signal:
        if re.search(r"\b(clinic|doctor visit|copay|prescription)\b", sanitized) and re.search(
            r"\b(urgent|emergency|acute|pain|sick|fever|infection)\b", sanitized
        ):
            return True, "Urgent medical visit/prescription verified."

    return False, "Standard discretionary or non-emergency spend requires reflection cooldown."


def distill_short_tag(
    utterance: str,
    category: Optional[str] = None,
    merchant_name: Optional[str] = None
) -> str:
    """
    Distills a user utterance or Coach query into a clean 1-5 word lowercase summary tag
    (e.g., 'groceries', 'takeout', 'gift for family', 'movie ticket', 'emergency er copay').
    """
    raw = (utterance or "").strip()
    lower = raw.lower()
    merch_lower = (merchant_name or "").lower()
    cat_lower = (category or "").lower()

    # 1. Check emergency tag first
    emerg, _ = is_genuine_emergency(raw, merchant_name or "", category or "")
    if emerg:
        if any(w in lower for w in ("er", "hospital", "urgent care", "ambulance", "copay", "doctor", "medical", "prescription", "insulin")):
            return "emergency medical care"
        if any(w in lower for w in ("tire", "car", "tow", "stranded")):
            return "emergency car repair"
        if any(w in lower for w in ("shutoff", "pipe", "utility", "power", "water")):
            return "emergency utility repair"
        return "emergency expense"

    # 2. High-signal semantic patterns matching user examples & common personal finance intents
    if "gift" in lower or "present" in lower:
        if any(w in lower for w in ("family", "mom", "mother", "dad", "father", "sister", "brother", "parents")):
            return "gift for family"
        if any(w in lower for w in ("friend", "best friend", "partner", "birthday")):
            return "gift for friend"
        return "gift purchase"

    if any(w in lower for w in ("sweep", "move to vault", "transfer to vault", "save to vault", "skim to vault")):
        return "vault sweep"

    if ("double-entry" in lower or "double entry" in lower) and any(w in lower for w in ("flow", "income", "bank", "rows")):
        return "bank double-entry flows"

    if any(w in lower for w in ("anomal", "deviation")):
        return "spending anomalies"

    if "freedom" in lower and any(w in lower for w in ("rent", "trajectory", "tracking")):
        return "freedom vs rent"

    if "velocity" in lower and "runway" in lower:
        return "velocity and runway"

    if "rollover" in lower or "streak" in lower:
        return "rollover streak"

    if "bank" in lower and any(w in lower for w in ("lock", "locked", "foundation", "protect", "rule")):
        return "bank lock rule"

    if any(w in lower for w in ("escape", "cooldown", "friction", "confession")):
        return "escape window rule"

    if any(w in lower for w in ("takeout", "take-out", "doordash", "uber eats", "grubhub", "delivery")):
        return "takeout"

    if any(w in lower or w in merch_lower for w in ("grocer", "supermarket", "safeway", "trader joe", "whole foods", "aldi", "kroger", "milk", "bread", "vegetables", "produce")):
        return "groceries"

    if "movie" in lower and "ticket" in lower:
        return "movie ticket"
    if "concert" in lower:
        return "concert ticket"
    if "steak" in lower or "steakhouse" in lower:
        return "steakhouse dinner"
    if "ramen" in lower:
        return "ramen dinner"
    if any(w in lower for w in ("dinner", "lunch", "brunch", "restaurant", "cafe", "coffee")):
        if "coffee" in lower or "cafe" in lower or "latte" in lower:
            return "coffee run"
        return "dining out"

    if any(w in lower or w in merch_lower for w in ("subway", "mta", "transit", "bus pass", "train", "metro")):
        return "subway transit pass"

    if any(w in lower for w in ("rent", "landlord", "lease")):
        return "apartment rent"
    if any(w in lower for w in ("electric", "water bill", "internet", "wifi", "utility")):
        return "utility bill"

    if any(w in lower for w in ("double-entry", "ledger", "velocity", "runway", "ag grid", "filtered")):
        return "ledger velocity audit"
    if "chart" in lower or "pie" in lower:
        return "chart breakdown"

    # 3. Clean phrase extraction fallback (2-4 meaningful words, stripping dollar amounts & punctuation)
    cleaned = re.sub(r"\$\s*\d+(?:\.\d{1,2})?", " ", lower)
    cleaned = re.sub(r"\b\d+(?:\.\d{1,2})?\s*(?:dollars?|bucks?|usd|cents?)\b", " ", cleaned)
    cleaned = re.sub(r"\b(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand)\s*(?:dollars?|bucks?|usd|cents?)\b", " ", cleaned)
    cleaned = re.sub(r"[^a-z0-9\s'-]", " ", cleaned)
    tokens = [t.strip("'-") for t in cleaned.split() if t.strip("'-")]

    # Stop-words stripped only from leading/trailing filler when distilling tags
    filler_tokens = _FILLER_WORDS | {"on", "in", "at", "by", "for", "with", "about"}

    meaningful: List[str] = []
    for idx, tok in enumerate(tokens):
        if tok in ("for", "of") and meaningful and idx + 1 < len(tokens) and tokens[idx + 1] not in filler_tokens:
            meaningful.append(tok)
        elif tok not in filler_tokens and len(tok) > 1:
            meaningful.append(tok)
        if len(meaningful) >= 4:
            break

    if meaningful:
        # Trim leading and trailing prepositions
        while meaningful and meaningful[0] in ("for", "of", "on", "in", "at", "by", "with", "about"):
            meaningful.pop(0)
        while meaningful and meaningful[-1] in ("for", "of", "on", "in", "at", "by", "with", "about"):
            meaningful.pop()
        if meaningful:
            return " ".join(meaningful)[:60]

    if cat_lower and cat_lower not in ("other", "general"):
        return cat_lower.replace("_", " ")[:60]

    return "general spend"


def normalize_short_tag(
    candidate_tag: Optional[str],
    fallback_utterance: str = "",
    category: Optional[str] = None,
    merchant_name: Optional[str] = None
) -> str:
    """
    Validates and normalizes an LLM-proposed `short_tag` so it is guaranteed to be
    1-5 concise lowercase words (<= 60 chars). Falls back to `distill_short_tag` if empty or noisy.
    """
    if candidate_tag and isinstance(candidate_tag, str):
        cleaned = re.sub(r"\$\d+(?:\.\d{1,2})?", "", candidate_tag.lower())
        cleaned = re.sub(r"[^a-z0-9\s'-]", " ", cleaned)
        words = [w for w in cleaned.split() if w]
        if 1 <= len(words) <= 5:
            normalized = " ".join(words)[:60].strip()
            if normalized and normalized not in ("none", "null", "n a", "unknown"):
                return normalized
    return distill_short_tag(fallback_utterance, category=category, merchant_name=merchant_name)


def _tokenize_for_rag(text: str) -> Set[str]:
    cleaned = re.sub(r"[^a-z0-9\s]", " ", (text or "").lower())
    return {w for w in cleaned.split() if len(w) > 2 and w not in _FILLER_WORDS}


async def retrieve_rag_context(
    session: AsyncSession,
    user_id: UUID,
    query_utterance: str,
    limit: int = 6
) -> Dict[str, Any]:
    """
    Retrieves lightweight RAG memory context from historical Intents, Overrides,
    and Coach messages recorded for `user_id`, indexed by `short_tag`.

    Returns:
        Dict with:
          - current_short_tag: distilled tag for current query
          - matched_records: top relevant/recent historical items
          - tag_rollup: aggregated spend counts & cents per short_tag
          - prompt_block: formatted string ready for LLM prompt injection
    """
    current_tag = distill_short_tag(query_utterance)
    query_tokens = _tokenize_for_rag(f"{query_utterance} {current_tag}")

    # Map bucket IDs -> kind names
    b_res = await session.exec(select(Bucket).where(Bucket.user_id == user_id))
    bucket_map = {b.id: b.kind for b in b_res.all()}

    # 1. Fetch recent Intents for user
    intent_stmt = (
        select(Intent)
        .where(Intent.user_id == user_id)
        .order_by(col(Intent.created_at).desc())
        .limit(40)
    )
    intents = (await session.exec(intent_stmt)).all()

    # 2. Fetch recent Overrides for user
    ov_stmt = (
        select(Override)
        .where(Override.user_id == user_id)
        .order_by(col(Override.created_at).desc())
        .limit(15)
    )
    overrides = (await session.exec(ov_stmt)).all()

    # 3. Fetch recent CoachMessages across user's threads (excluding very latest identical message)
    cm_stmt = (
        select(CoachMessage)
        .join(CoachThread, CoachMessage.thread_id == CoachThread.id)
        .where(CoachThread.user_id == user_id)
        .where(CoachMessage.short_tag.is_not(None))  # type: ignore[union-attr]
        .order_by(col(CoachMessage.created_at).desc())
        .limit(20)
    )
    coach_msgs = (await session.exec(cm_stmt)).all()

    candidates: List[Tuple[float, Dict[str, Any]]] = []
    tag_stats: Dict[str, Dict[str, int]] = {}

    for idx, it in enumerate(intents):
        tag = it.short_tag or distill_short_tag(it.utterance, category=it.category, merchant_name=it.merchant_name)
        bucket_kind = bucket_map.get(it.source_bucket_id, it.recommended_bucket or "daily")  # type: ignore[arg-type]

        if it.status in ("settled", "allowed", "executing", "override_approved", "needs_override"):
            stat = tag_stats.setdefault(tag, {"count": 0, "total_cents": 0})
            stat["count"] += 1
            stat["total_cents"] += it.amount

        doc_tokens = _tokenize_for_rag(f"{tag} {it.category or ''} {it.utterance} {it.merchant_name or ''}")
        overlap = len(query_tokens & doc_tokens)
        recency_score = max(0.1, 1.0 - (idx * 0.03))
        score = (overlap * 3.0) + (2.0 if tag == current_tag else 0.0) + recency_score

        candidates.append((
            score,
            {
                "source": "intent",
                "short_tag": tag,
                "amount_cents": it.amount,
                "bucket": bucket_kind,
                "category": it.category or "general",
                "status": it.status,
                "is_emergency": bool(it.is_emergency),
                "date": it.created_at.strftime("%Y-%m-%d"),
                "utterance": it.utterance[:80],
            },
        ))

    for idx, ov in enumerate(overrides):
        tag = ov.short_tag or distill_short_tag(ov.body)
        doc_tokens = _tokenize_for_rag(f"{tag} {ov.body}")
        overlap = len(query_tokens & doc_tokens)
        score = (overlap * 2.5) + (1.5 if ov.is_emergency else 0.3) + max(0.1, 0.8 - idx * 0.05)
        candidates.append((
            score,
            {
                "source": "override",
                "short_tag": tag,
                "amount_cents": 0,
                "bucket": "bank",
                "category": "emergency" if ov.is_emergency else "override",
                "status": ov.status,
                "is_emergency": bool(ov.is_emergency),
                "date": ov.created_at.strftime("%Y-%m-%d"),
                "utterance": ov.body[:80],
            },
        ))

    for idx, cm in enumerate(coach_msgs):
        if cm.role == "user" and cm.content.strip() == query_utterance.strip():
            continue
        tag = cm.short_tag or distill_short_tag(cm.content)
        doc_tokens = _tokenize_for_rag(f"{tag} {cm.content}")
        overlap = len(query_tokens & doc_tokens)
        if overlap > 0:
            score = (overlap * 2.0) + max(0.1, 0.6 - idx * 0.03)
            candidates.append((
                score,
                {
                    "source": "coach_memory",
                    "short_tag": tag,
                    "amount_cents": 0,
                    "bucket": "coach",
                    "category": "coaching",
                    "status": cm.role,
                    "is_emergency": False,
                    "date": cm.created_at.strftime("%Y-%m-%d"),
                    "utterance": cm.content[:80],
                },
            ))

    candidates.sort(key=lambda pair: pair[0], reverse=True)
    matched_records = [item for _, item in candidates[:limit]]

    tag_rollup = [
        {
            "short_tag": t,
            "count": vals["count"],
            "total_cents": vals["total_cents"],
        }
        for t, vals in sorted(tag_stats.items(), key=lambda kv: kv[1]["total_cents"], reverse=True)[:8]
    ]

    if matched_records or tag_rollup:
        rollup_lines = [
            f"  * '{r['short_tag']}': {r['count']}x (${r['total_cents'] / 100:.2f} total)"
            for r in tag_rollup[:5]
        ]
        memory_lines = [
            f"  * [{m['date']}] tag='{m['short_tag']}' | {m['source']} | "
            f"${m['amount_cents'] / 100:.2f} ({m['bucket']}, {m['status']}) — {m['utterance']}"
            for m in matched_records[:5]
        ]
        prompt_block = (
            "RAG Historical Short-Tag Memory:\n"
            + ("- Top Recorded Spend Tags:\n" + "\n".join(rollup_lines) + "\n" if rollup_lines else "")
            + ("- Relevant Past Activity:\n" + "\n".join(memory_lines) + "\n" if memory_lines else "")
        )
    else:
        prompt_block = "RAG Historical Short-Tag Memory: No prior tagged history recorded yet.\n"

    return {
        "current_short_tag": current_tag,
        "matched_records": matched_records,
        "tag_rollup": tag_rollup,
        "prompt_block": prompt_block,
    }
