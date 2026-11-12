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

export async function executeIntent(intentId, returnUrl = null) {
  const body = returnUrl ? { return_url: returnUrl } : {};
  const res = await fetch(`${API_BASE}/intents/${intentId}/execute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to execute intent');
  }
  return res.json();
}

export async function getIntentOrderStatus(intentId) {
  const res = await fetch(`${API_BASE}/intents/${intentId}/order-status`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch PayPal order status');
  }
  return res.json();
}

export async function captureIntent(intentId, paypalOrderId, payerId = null) {
  const payload = { paypal_order_id: paypalOrderId };
  if (payerId) payload.payer_id = payerId;

  const res = await fetch(`${API_BASE}/intents/${intentId}/capture`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to capture PayPal order');
  }
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

export async function fetchCoachStatus() {
  const res = await fetch(`${API_BASE}/coach/status`);
  if (!res.ok) throw new Error('Failed to fetch coach status');
  return res.json();
}

export async function fetchPayPalBalance() {
  const res = await fetch(`${API_BASE}/paypal/balance`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to detect PayPal balance');
  }
  return res.json();
}

export async function syncPayPalBalance(overrideBalanceCents = null) {
  const payload =
    overrideBalanceCents !== null ? { override_balance_cents: overrideBalanceCents } : {};
  const res = await fetch(`${API_BASE}/paypal/sync-balance`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to sync PayPal balance');
  }
  return res.json();
}

export async function fetchPolicy() {
  const res = await fetch(`${API_BASE}/me/policy`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to load policy');
  }
  return res.json();
}

/**
 * Update budget policy envelopes and rules (including daily_amount, freedom_monthly_amount, bills_monthly_amount, vault_skim_bps).
 */
export async function updatePolicy(policyUpdates) {
  const res = await fetch(`${API_BASE}/me/policy`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(policyUpdates)
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to update bucket policy');
  }
  return res.json();
}

/**
 * Stage an evaluated Intent or recurring obligation into the Batch Dispatcher staging queue.
 * @param {Object} data - { intent_id, recipient_email, amount_cents, currency, category, source_bucket, note }
 */
export async function stageIntentToBatch(data) {
  const res = await fetch(`${API_BASE}/bills/batch-dispatcher/stage-intent`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(data),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to stage payment in Batch Dispatcher');
  }
  return res.json();
}

/**
 * Query live PayPal status and synchronized database state for a batch payout.
 * @param {string} payoutBatchId - PayPal Payout Batch ID
 */
export async function getBatchPayoutStatus(payoutBatchId) {
  const res = await fetch(`${API_BASE}/bills/batch-dispatcher/status/${payoutBatchId}`);
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || 'Failed to fetch batch payout status');
  }
  return res.json();
}
