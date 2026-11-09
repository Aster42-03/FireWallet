"""
Unified Monolithic Financial Coach Agent (`CoachDecision` + RAG + Guardrails)
=============================================================================
Implements the single-call LLM architecture (Groq `llama-3.3-70b-versatile` primary,
`gpt-4o-mini` fallback, deterministic offline heuristic fallback) backed by strict
Python `LedgerEngine` guardrails:

1. **The Brain & Voice (Single LLM Call)**:
   Evaluates the user's message against Trinity bucket balances, AG Grid telemetry,
   and RAG historical `short_tag` memory, returning both conversational text (`reply`)
   AND structured decision metadata (`CoachDecision`) in one JSON packet.
2. **The Guardrails & Execution (`LedgerEngine`)**:
   The LLM never touches money directly. Deterministic Python logic validates bucket
   caps, enforces Vault locks, grants 0-second zero-delay approval for verified
   medical/safety emergencies, and pre-configures a 1-tap `ActionCard` button.
"""

import json
import re
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.agents.shared.llm_client import llm_client
from app.agents.rag import (
    distill_short_tag,
    is_genuine_emergency,
    normalize_short_tag,
    parse_amount_cents_from_text,
    retrieve_rag_context,
)
from app.models.bucket import Bucket
from app.models.coach import CoachThread, CoachMessage
from app.models.intent import AgentRun, Intent, Override
from app.models.batch_payment import BatchPaymentItem
from app.ledger.engine import LedgerEngine
from app.analytics.summary import get_hud_summary
from app.analytics.deep_analytics import query_deep_ledger, detect_spending_anomalies
from app.schemas.common import ActionCard, CoachDecision


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _extract_amount_cents(utterance: str, llm_amount: Optional[Any]) -> Optional[int]:
    """Deterministically extracts minor-unit cents from `$XX`, dollar words, or LLM integer."""
    parsed = parse_amount_cents_from_text(utterance)
    if parsed is not None:
        return parsed
    if isinstance(llm_amount, (int, float)) and llm_amount > 0:
        return int(llm_amount)
    return None


async def handle_coach_query(
    session: AsyncSession,
    user_id: UUID,
    utterance: str,
    thread_id: Optional[UUID] = None,
    chart_id: Optional[str] = None,
    filter_context: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Executes the Unified Monolithic Coach workflow:
    1. Distills & records `short_tag` on user message.
    2. Retrieves RAG historical `short_tag` context + live Trinity balances / AG Grid telemetry.
    3. Executes ONE single structured JSON LLM call (`CoachDecision`).
    4. Applies deterministic `LedgerEngine` guardrails (including 0-delay emergency unlock)
       to construct a pre-filled 1-tap `ActionCard`.
    5. Persists assistant reply, `short_tag`, `action_card_json`, and `AgentRun` audit log.
    """
    if not thread_id:
        thread = CoachThread(user_id=user_id, title=utterance[:40])
        session.add(thread)
        await session.commit()
        await session.refresh(thread)
        thread_id = thread.id

    # Retrieve RAG context BEFORE inserting current message so we don't match current message to itself
    rag_ctx = await retrieve_rag_context(session=session, user_id=user_id, query_utterance=utterance)
    initial_tag = rag_ctx["current_short_tag"]

    user_msg = CoachMessage(
        thread_id=thread_id,
        role="user",
        content=utterance,
        short_tag=initial_tag,
        chart_id=chart_id,
    )
    session.add(user_msg)
    await session.commit()

    balances = await LedgerEngine.get_bucket_balances(session, user_id)
    hud_data = await get_hud_summary(session, user_id)

    citations: Dict[str, Any] = {"buckets": []}
    suggest_intent: Optional[Dict[str, Any]] = None

    # Build live financial + telemetry context
    balance_block = (
        f"Current Trinity Bucket Balances:\n"
        f"- Bank Foundation (Protected): ${balances.get('bank', {}).get('available', 0) / 100:.2f}\n"
        f"- Daily Allowance (Essentials + Rollover): ${balances.get('daily', {}).get('available', 0) / 100:.2f}\n"
        f"- Freedom Envelope (Discretionary Fun): ${balances.get('freedom', {}).get('available', 0) / 100:.2f}\n"
        f"- Locked Savings Vault (Strictly No-Spend): ${balances.get('vault', {}).get('available', 0) / 100:.2f}\n"
        f"- Reserved Bills (Contractual Only): ${balances.get('bills', {}).get('available', 0) / 100:.2f}\n"
    )

    if filter_context:
        selected_rows = filter_context.get("selected_rows") or []
        deep_res = await query_deep_ledger(
            session=session,
            user_id=user_id,
            category=filter_context.get("category"),
            bucket=filter_context.get("bucket"),
            state=filter_context.get("state"),
            entry_kind=filter_context.get("entry_kind"),
            limit=50,
        )
        anomalies = await detect_spending_anomalies(session=session, user_id=user_id)
        aggs = deep_res["aggregates"]
        vel = aggs.get("velocity_metrics", {})

        selected_summary = ""
        if selected_rows:
            selected_total = sum(abs(r.get("amount", 0)) for r in selected_rows)
            item_descriptions = [
                f"{r.get('utterance', '')} (${abs(r.get('amount', 0)) / 100:.2f} from {r.get('bucket', '')})"
                for r in selected_rows[:4]
            ]
            selected_summary = (
                f"- User Selected Ledger Rows: {len(selected_rows)} transactions (Total: ${selected_total / 100:.2f})\n"
                f"- Selected Items: {item_descriptions}\n"
            )

        context_str = (
            f"{balance_block}\n"
            f"Ledger Active Filter & Deep Audit Context:\n"
            f"- Filter: {filter_context}\n"
            f"- Filtered Count: {deep_res['total_count']} transactions\n"
            f"- Filtered Debits: ${aggs.get('total_debits', 0) / 100:.2f} | Credits: ${aggs.get('total_credits', 0) / 100:.2f}\n"
            f"- Merchant Outflows: ${aggs.get('merchant_outflows', 0) / 100:.2f}\n"
            f"- Internal Bank Allocations: ${aggs.get('internal_transfers_volume', 0) / 100:.2f}\n"
            f"- Double-Entry Zero-Sum Reconciled: {aggs.get('double_entry_balanced', True)}\n"
            f"- Daily Living Burn Rate: ${vel.get('daily_burn_rate', 3400) / 100:.2f}/day\n"
            f"- Projected Daily Runway: {vel.get('daily_runway_days', 1.5)} days\n"
            f"- Freedom Monthly Burn: {vel.get('freedom_burn_pct', 40.0)}% burned\n"
            f"- Rollover Retained: ${vel.get('rollover_retained', 1200) / 100:.2f}\n"
            f"{selected_summary}"
            f"- Detected Anomalies: {anomalies[:3]}\n\n"
            f"{rag_ctx['prompt_block']}"
        )
        citations["deep_ledger"] = {
            "filtered_count": deep_res["total_count"],
            "selected_count": len(selected_rows),
            "zero_sum_balanced": aggs.get("double_entry_balanced", True),
            "daily_burn_rate": vel.get("daily_burn_rate", 3400),
            "daily_runway_days": vel.get("daily_runway_days", 1.5),
        }
        citations["buckets"] = [filter_context.get("bucket")] if filter_context.get("bucket") else ["bank", "daily", "freedom"]
    elif chart_id:
        chart_obj = next((c for c in hud_data["charts"] if c["id"] == chart_id), None)
        context_str = (
            f"{balance_block}\n"
            f"HUD Chart '{chart_id}':\n{json.dumps(chart_obj)}\n\n"
            f"{rag_ctx['prompt_block']}"
        )
        citations["chart_id"] = chart_id
        citations["buckets"] = ["daily", "freedom"]
    else:
        context_str = f"{balance_block}\n{rag_ctx['prompt_block']}"
        citations["buckets"] = ["daily", "freedom"]

    system_prompt = (
        "You are the Unified Trinity Coach for FireWallet. In a SINGLE structured JSON response, "
        "evaluate the user's message against their live Trinity bucket balances, ledger telemetry, "
        "and RAG historical short-tag memory. Write a warm, concise, plain-spoken conversational `reply` "
        "AND decide the structured action metadata.\n\n"
        "Return STRICT JSON matching this exact schema:\n"
        "{\n"
        '  "reply": "Friendly conversational coaching response (mention Double-Entry & Ledger if analyzing grid)",\n'
        '  "status": "accepted | rejected | refer_to_coach | info",\n'
        '  "action_type": "paypal_checkout | sweep_to_vault | open_override | none",\n'
        '  "short_tag": "concise 2-5 word lowercase tag e.g. groceries, takeout, gift for family, movie ticket",\n'
        '  "category": "groceries | eating_out | entertainment | transit | utilities | gifts | savings | emergency | analytics",\n'
        '  "necessity": "daily_living | freedom | bill",\n'
        '  "target_bucket": "daily | freedom | bills | bank | vault",\n'
        '  "amount_cents": 1500 or null,\n'
        '  "merchant_name": "optional merchant or null",\n'
        '  "is_emergency": false,\n'
        '  "rationale": "1-sentence policy summary",\n'
        '  "flags": []\n'
        "}\n"
        "Rules: Never allow spending from `vault`. Mark `is_emergency: true` ONLY for genuine medical/ER/hospital/"
        "stranded/utility-shutoff emergencies (zero cooldown), never for celebrations or luxury splurges."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": f"Context:\n{context_str}\n\nUser Question:\n{utterance}"},
    ]

    start_time = time.time()
    raw_response = await llm_client.chat_completion(messages, temperature=0.2, json_mode=True)
    latency_ms = int((time.time() - start_time) * 1000)

    try:
        parsed_json = json.loads(raw_response)
        if not isinstance(parsed_json, dict):
            raise ValueError("Expected JSON object")
    except Exception:
        parsed_json = {
            "reply": raw_response if isinstance(raw_response, str) and raw_response.strip() else "Let's review how this fits your Trinity buckets.",
            "status": "info",
            "action_type": "none",
            "short_tag": initial_tag,
        }

    # Normalize short_tag & emergency verification deterministically
    category = str(parsed_json.get("category") or "general")
    merchant_name = parsed_json.get("merchant_name")
    short_tag = normalize_short_tag(
        parsed_json.get("short_tag"),
        fallback_utterance=utterance,
        category=category,
        merchant_name=merchant_name,
    )
    # Keep user message short_tag aligned with refined tag
    user_msg.short_tag = short_tag
    session.add(user_msg)

    det_emerg, emerg_reason = is_genuine_emergency(utterance, merchant_name or "", category)
    amount_cents = _extract_amount_cents(utterance, parsed_json.get("amount_cents"))
    reply_text = str(parsed_json.get("reply") or "Here is how your Trinity buckets look right now.")

    # Ensure Deep Ledger interrogation always explicitly references Double-Entry / Ledger for clarity
    if filter_context and ("Double-Entry" not in reply_text and "Ledger" not in reply_text):
        reply_text = f"Double-Entry Ledger Analysis: {reply_text}"

    action_card: Optional[ActionCard] = None
    decision_status = str(parsed_json.get("status") or "info")
    action_type = str(parsed_json.get("action_type") or "none")
    necessity = str(parsed_json.get("necessity") or "freedom")
    target_bucket = str(parsed_json.get("target_bucket") or "freedom")

    # --------------------------------------------------------------------------
    # Deterministic Python Guardrails (`LedgerEngine` verification & ActionCard)
    # --------------------------------------------------------------------------
    lower_utt = utterance.lower()
    is_sweep_query = action_type == "sweep_to_vault" or any(
        w in lower_utt for w in ("sweep", "save to vault", "move to vault", "transfer to vault", "lock in vault")
    )
    is_stage_query = (
        action_type == "stage_batch"
        or any(w in lower_utt for w in ("stage", "batch queue", "batch payment", "queue payment", "stage bill", "stage payment", "add to batch", "queue in batch"))
        or (
            any(w in lower_utt for w in ("bill", "rent", "utility", "electric", "water", "internet", "wifi"))
            and any(w in lower_utt for w in ("stage", "queue", "batch"))
        )
    )

    if is_sweep_query and not filter_context and not chart_id:
        sweep_cents = amount_cents or 2500
        bank_avail = balances.get("bank", {}).get("available", 0)
        if bank_avail >= sweep_cents:
            decision_status = "accepted"
            action_type = "sweep_to_vault"
            target_bucket = "vault"
            short_tag = "vault sweep"
            action_card = ActionCard(
                action_type="sweep_to_vault",
                label=f"Sweep ${sweep_cents / 100:.2f} to Vault (1-Tap)",
                short_tag=short_tag,
                utterance=utterance[:120],
                amount_cents=sweep_cents,
                category="savings",
                necessity="daily_living",
                target_bucket="vault",
                is_emergency=False,
                verdict="accepted",
            )
            citations["buckets"] = ["bank", "vault"]
        else:
            decision_status = "rejected"
            action_type = "none"
            reply_text = (
                f"You currently have ${bank_avail / 100:.2f} available in your Bank Foundation, "
                f"so sweeping ${sweep_cents / 100:.2f} isn't possible right now."
            )

    elif is_stage_query and amount_cents and amount_cents > 0 and not filter_context and not chart_id:
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", utterance)
        recipient_email = email_match.group(0) if email_match else (merchant_name if (merchant_name and "@" in merchant_name) else "billing@service.com")
        cat_name = (category if category and category != "general" else "bills").capitalize()
        title = short_tag.title() if short_tag and short_tag != "general spend" else (merchant_name or f"{cat_name} Payment")

        batch_item = BatchPaymentItem(
            user_id=user_id,
            title=title,
            recipient_name=title,
            amount_minor=amount_cents,
            category=cat_name,
            currency="USD",
            source_bucket="bills",
            status="pending_approval",
            recommended=True,
            recipient_email=recipient_email,
            payee_email=recipient_email,
            note=utterance[:120],
        )
        session.add(batch_item)
        await session.commit()
        await session.refresh(batch_item)

        decision_status = "accepted"
        action_type = "stage_batch"
        target_bucket = "bills"
        necessity = "bill"

        action_card = ActionCard(
            action_type="stage_batch",
            label=f"View in Batch Dispatcher (${amount_cents / 100:.2f})",
            short_tag=short_tag,
            utterance=utterance[:120],
            amount_cents=amount_cents,
            category=cat_name.lower(),
            necessity="bill",
            target_bucket="bills",
            merchant_name=recipient_email,
            is_emergency=False,
            verdict="accepted",
        )
        reply_text = (
            f"I've staged your payment of ${amount_cents / 100:.2f} to {recipient_email} into the **Batch Dispatcher** "
            f"under your isolated Reserved Bills reserve. You can review and authorize the batch execution anytime in the Batch Dispatcher."
        )
        citations["buckets"] = ["bills"]

    elif amount_cents and amount_cents > 0 and not filter_context and not chart_id:
        # Determine target bucket cleanly
        if target_bucket not in ("daily", "freedom", "bills", "bank", "vault"):
            target_bucket = "freedom" if necessity == "freedom" else "daily"
        if necessity not in ("bill", "daily_living", "freedom", "ambiguous"):
            necessity = "freedom" if target_bucket == "freedom" else "daily_living"

        if det_emerg:
            # Valid emergency -> ZERO cooldown delay! Route to Locked Savings Vault (BUG-008).
            vault_avail = balances.get("vault", {}).get("available", 0)
            bank_avail = balances.get("bank", {}).get("available", 0)
            total_emerg_avail = vault_avail + bank_avail

            if total_emerg_avail >= amount_cents:
                bucket_stmt = select(Bucket).where(Bucket.user_id == user_id).where(Bucket.kind == "vault")
                bucket_obj = (await session.exec(bucket_stmt)).first()

                pre_intent = Intent(
                    user_id=user_id,
                    utterance=utterance,
                    short_tag=short_tag,
                    amount=amount_cents,
                    currency="USD",
                    merchant_name=merchant_name,
                    category=category if category != "general" else "emergency",
                    necessity="daily_living",
                    recommended_bucket="vault",
                    source_bucket_id=bucket_obj.id if bucket_obj else None,
                    is_emergency=True,
                    status="allowed",
                )
                session.add(pre_intent)
                await session.commit()
                await session.refresh(pre_intent)

                decision_status = "accepted"
                action_type = "paypal_checkout"
                target_bucket = "vault"
                action_card = ActionCard(
                    action_type="paypal_checkout",
                    label=f"Emergency Autonomous Pay ${amount_cents / 100:.2f} via Vault (0s Delay)",
                    short_tag=short_tag,
                    utterance=utterance[:120],
                    amount_cents=amount_cents,
                    category=pre_intent.category or "emergency",
                    necessity="daily_living",
                    target_bucket="vault",
                    merchant_name=merchant_name,
                    intent_id=pre_intent.id,
                    is_emergency=True,
                    verdict="accepted",
                )
                reply_text = (
                    f"Verified genuine emergency: {emerg_reason}\n\n"
                    f"Empowered autonomous payment of ${amount_cents / 100:.2f} routed from your **Locked Savings Vault** "
                    f"with 0s cooldown bypass."
                )
                citations["buckets"] = ["vault"]
            else:
                decision_status = "rejected"
                action_type = "none"
                reply_text = (
                    f"This verified emergency requires ${amount_cents / 100:.2f}, but your combined emergency reserves "
                    f"(Vault ${vault_avail / 100:.2f} + Bank ${bank_avail / 100:.2f} = ${total_emerg_avail / 100:.2f}) "
                    f"are insufficient."
                )
                citations["buckets"] = ["vault", "bank"]
        elif target_bucket == "vault" or "from vault" in lower_utt or "raid vault" in lower_utt:
            decision_status = "rejected"
            action_type = "none"
            reply_text = (
                "Your **Locked Savings Vault** cannot be spent directly under Trinity firewall rules. "
                "If this is an urgent expense, we can evaluate your Daily or Bank Foundation instead."
            )
            citations["buckets"] = ["vault"]
        else:
            # Standard non-emergency spend: run deterministic LedgerEngine.can_spend
            is_ok, pol_status, pol_rationale = await LedgerEngine.can_spend(
                session=session,
                user_id=user_id,
                amount_minor=amount_cents,
                source_kind=target_bucket,
                necessity=necessity,
            )

            bucket_stmt = select(Bucket).where(Bucket.user_id == user_id).where(Bucket.kind == target_bucket)
            bucket_obj = (await session.exec(bucket_stmt)).first()

            pre_intent = Intent(
                user_id=user_id,
                utterance=utterance,
                short_tag=short_tag,
                amount=amount_cents,
                currency="USD",
                merchant_name=merchant_name,
                category=category,
                necessity=necessity,
                recommended_bucket=target_bucket,
                source_bucket_id=bucket_obj.id if bucket_obj else None,
                is_emergency=False,
                status=pol_status,
            )
            session.add(pre_intent)
            await session.commit()
            await session.refresh(pre_intent)

            if is_ok and pol_status == "allowed":
                decision_status = "accepted"
                action_type = "paypal_checkout"
                action_card = ActionCard(
                    action_type="paypal_checkout",
                    label=f"Pay ${amount_cents / 100:.2f} via PayPal ({target_bucket.capitalize()})",
                    short_tag=short_tag,
                    utterance=utterance[:120],
                    amount_cents=amount_cents,
                    category=category,
                    necessity=necessity,
                    target_bucket=target_bucket,
                    merchant_name=merchant_name,
                    intent_id=pre_intent.id,
                    is_emergency=False,
                    verdict="accepted",
                )
                citations["buckets"] = [target_bucket]
            elif pol_status == "needs_override":
                decision_status = "refer_to_coach"
                action_type = "open_override"
                avail_in_target = balances.get(target_bucket, {}).get("available", 0)
                if "override" not in reply_text.lower() and "exceeds" not in reply_text.lower():
                    reply_text = (
                        f"${amount_cents / 100:.2f} for **{short_tag}** exceeds your **{target_bucket.capitalize()}** "
                        f"available balance (${avail_in_target / 100:.2f}). {pol_rationale} "
                        f"If you still want to proceed from your Bank Foundation, use the Escape Window below (200-char reflection + 3m cooldown)."
                    )
                action_card = ActionCard(
                    action_type="open_override",
                    label=f"Open Escape Window (${amount_cents / 100:.2f})",
                    short_tag=short_tag,
                    utterance=utterance[:120],
                    amount_cents=amount_cents,
                    category=category,
                    necessity=necessity,
                    target_bucket=target_bucket,
                    merchant_name=merchant_name,
                    intent_id=pre_intent.id,
                    is_emergency=False,
                    verdict="refer_to_coach",
                )
                citations["buckets"] = [target_bucket, "bank"]
            else:
                decision_status = "rejected"
                action_type = "none"

        # Preserve `suggest_intent` payload for backwards-compatible clients/tests
        suggest_intent = {
            "intent_id": str(action_card.intent_id) if action_card and action_card.intent_id else None,
            "utterance": utterance[:60],
            "short_tag": short_tag,
            "amount": amount_cents,
            "category": category,
            "target_bucket": target_bucket,
        }

    decision_obj = CoachDecision(
        reply=reply_text,
        status=decision_status,
        action_type=action_type,
        short_tag=short_tag,
        category=category,
        necessity=necessity,
        target_bucket=target_bucket,
        amount_cents=amount_cents,
        merchant_name=merchant_name,
        is_emergency=det_emerg,
        rationale=str(parsed_json.get("rationale") or emerg_reason),
        flags=list(parsed_json.get("flags") or []),
    )

    citations["rag_memory"] = {
        "current_short_tag": short_tag,
        "matched_count": len(rag_ctx["matched_records"]),
        "top_tags": rag_ctx["tag_rollup"][:5],
        "matches": rag_ctx["matched_records"][:3],
    }

    asst_msg = CoachMessage(
        thread_id=thread_id,
        role="assistant",
        content=reply_text,
        short_tag=short_tag,
        citations_json=json.dumps(citations),
        suggest_intent_json=json.dumps(suggest_intent) if suggest_intent else None,
        action_card_json=action_card.model_dump_json() if action_card else None,
    )
    session.add(asst_msg)

    agent_run = AgentRun(
        kind="insights",
        thread_id=thread_id,
        model=llm_client.model,
        prompt_version="v3-unified-coach-rag",
        latency_ms=latency_ms,
        raw_response=raw_response,
        parsed=decision_obj.model_dump_json(),
    )
    session.add(agent_run)

    await session.commit()
    await session.refresh(asst_msg)

    return {
        "thread_id": thread_id,
        "message_id": asst_msg.id,
        "reply": reply_text,
        "short_tag": short_tag,
        "decision": decision_obj.model_dump(),
        "action_card": action_card.model_dump() if action_card else None,
        "citations": citations,
        "suggest_intent": suggest_intent,
        "provider": llm_client.active_provider,
        "model": llm_client.model,
    }
