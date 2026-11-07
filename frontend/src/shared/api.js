/**
 * FireWallet Client API Service
 * ==============================
 * Centralized fetch client wrapping backend FastAPI v1 endpoints, including:
 * - Trinity Buckets, HUD Summary & AG Grid Deep Ledger
 * - Quick Intent Firewall & Short-Tag RAG History
 * - Escape Window & Zero-Delay Emergency Overrides
 * - Unified Monolithic Coach (`CoachDecision` + 1-Tap `ActionCard` Execution)
 */

const API_BASE = '/api/v1';

export async function fetchBuckets() {
  const res = await fetch(`${API_BASE}/buckets`);
  if (!res.ok) throw new Error('Failed to load buckets');
  return res.json();
}

export async function fetchStatsSummary() {
  const res = await fetch(`${API_BASE}/stats/summary`);
  if (!res.ok) throw new Error('Failed to load summary stats');
  return res.json();
}

export async function fetchDeepLedger(params = {}) {
  const query = new URLSearchParams(params).toString();
  const res = await fetch(`${API_BASE}/analytics/deep-ledger${query ? `?${query}` : ''}`);
  if (!res.ok) throw new Error('Failed to load deep ledger');
  return res.json();
}

export async function submitIntent(utterance, amountCents, merchantName = '', shortTag = undefined) {
  const payload = {
    utterance,
    amount: amountCents,
    currency: 'USD',
    merchant_name: merchantName
  };
  if (shortTag) payload.short_tag = shortTag;

  const res = await fetch(`${API_BASE}/intents`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Idempotency-Key': `client-${Date.now()}`
    },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to submit intent');
  }
  return res.json();
}

export async function fetchIntentTags() {
  const res = await fetch(`${API_BASE}/intents/tags`);
  if (!res.ok) throw new Error('Failed to load recorded intent tags');
  return res.json();
}

export async function executeIntent(intentId) {
  const res = await fetch(`${API_BASE}/intents/${intentId}/execute`, {
    method: 'POST'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to execute intent');
  }
  return res.json();
}

export async function captureIntent(intentId, paypalOrderId) {
  const res = await fetch(`${API_BASE}/intents/${intentId}/capture`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ paypal_order_id: paypalOrderId })
  });
  if (!res.ok) throw new Error('Failed to capture PayPal order');
  return res.json();
}

export async function submitOverride(intentId, body) {
  const res = await fetch(`${API_BASE}/overrides`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ intent_id: intentId, body })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to submit override');
  }
  return res.json();
}

export async function checkCooldown(overrideId) {
  const res = await fetch(`${API_BASE}/overrides/${overrideId}/check-cooldown`, {
    method: 'POST'
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Cooldown check failed');
  }
  return res.json();
}

export async function sendCoachMessage(
  utterance,
  chartId = null,
  filterContext = null,
  threadId = null,
  signal = undefined
) {
  const res = await fetch(`${API_BASE}/coach/messages`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    signal,
    body: JSON.stringify({
      utterance,
      chart_id: chartId,
      filter_context: filterContext,
      thread_id: threadId
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Coach is currently offline');
  }
  return res.json();
}

export async function executeCoachAction(actionCard, autoCaptureDemo = true) {
  const res = await fetch(`${API_BASE}/coach/execute-action`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      action_type: actionCard.action_type,
      utterance: actionCard.utterance,
      short_tag: actionCard.short_tag,
      amount_cents: actionCard.amount_cents,
      currency: actionCard.currency || 'USD',
      category: actionCard.category,
      necessity: actionCard.necessity,
      target_bucket: actionCard.target_bucket,
      merchant_name: actionCard.merchant_name,
      intent_id: actionCard.intent_id,
      is_emergency: Boolean(actionCard.is_emergency),
      auto_capture_demo: autoCaptureDemo
    })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to execute 1-tap Coach action');
  }
  return res.json();
}
