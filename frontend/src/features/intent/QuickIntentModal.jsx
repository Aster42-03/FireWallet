import React, { useState } from 'react';
import {
  X,
  ShieldCheck,
  ShieldAlert,
  Lock,
  ArrowRight,
  Loader2,
  ExternalLink,
  Tag,
  Sparkles,
  Zap,
  Layers,
  CheckCircle2
} from 'lucide-react';
import { submitIntent, executeIntent, captureIntent, stageIntentToBatch, getIntentOrderStatus } from '../../shared/api';
import { useToast } from '../notifications/ToastContext';

export default function QuickIntentModal({
  isOpen,
  onClose,
  onOpenOverride,
  onAskCoach,
  onOpenBatchDispatcher,
  onSuccess
}) {
  const { showToast } = useToast();
  const [amountStr, setAmountStr] = useState('');
  const [utterance, setUtterance] = useState('');
  const [merchant, setMerchant] = useState('');

  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [staging, setStaging] = useState(false);
  const [stagedSuccess, setStagedSuccess] = useState(false);
  const [batchEmail, setBatchEmail] = useState('');
  const [showEmailPrompt, setShowEmailPrompt] = useState(false);
  const [verdict, setVerdict] = useState(null);
  const [error, setError] = useState(null);

  // Interactive PayPal Sandbox Approval Loop states
  const [approvalState, setApprovalState] = useState(null); // { orderId, approvalUrl }
  const [capturing, setCapturing] = useState(false);
  const [captureError, setCaptureError] = useState(null);
  const [captureSuccess, setCaptureSuccess] = useState(null); // { captureId, orderId, bucket }

  React.useEffect(() => {
    if (!isOpen) {
      setVerdict(null);
      setError(null);
      setAmountStr('');
      setUtterance('');
      setMerchant('');
      setStagedSuccess(false);
      setShowEmailPrompt(false);
      setBatchEmail('');
      setStaging(false);
      setApprovalState(null);
      setCapturing(false);
      setCaptureError(null);
      setCaptureSuccess(null);
    }
  }, [isOpen]);

  const handleEvaluate = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    setStagedSuccess(false);
    setShowEmailPrompt(false);
    try {
      const cents = Math.round(parseFloat(amountStr || '0') * 100);
      if (isNaN(cents) || cents <= 0) {
        throw new Error('Please enter a valid positive dollar amount.');
      }
      const res = await submitIntent(utterance, cents, merchant);
      setVerdict(res);
      if (merchant && merchant.includes('@')) {
        setBatchEmail(merchant);
      }
    } catch (err) {
      setError(err.message || 'Evaluation failed');
    } finally {
      setLoading(false);
    }
  };

  // Auto-poll PayPal Order status while waiting for buyer approval
  React.useEffect(() => {
    if (!approvalState || capturing || captureSuccess || !verdict) return;

    const interval = setInterval(async () => {
      try {
        const statusData = await getIntentOrderStatus(verdict.id);
        if (statusData.order_status === 'APPROVED') {
          handleConfirmCapture(approvalState.orderId);
        }
      } catch (err) {
        // Quiet poll fail
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [approvalState, capturing, captureSuccess, verdict]);

  const handleExecutePayPal = async () => {
    if (!verdict) return;
    setExecuting(true);
    setError(null);
    setCaptureError(null);
    setApprovalState(null);
    setCaptureSuccess(null);

    try {
      const returnUrl = `${window.location.origin}/?paypal_return=true&intent_id=${verdict.id}`;
      const execRes = await executeIntent(verdict.id, returnUrl);

      if (!execRes.approval_url) {
        throw new Error('PayPal did not return a valid checkout approval URL.');
      }

      // Real interactive PayPal Sandbox flow
      setApprovalState({
        orderId: execRes.paypal_order_id,
        approvalUrl: execRes.approval_url,
      });

      // Open PayPal approval window
      window.open(execRes.approval_url, '_blank', 'noopener,noreferrer');
    } catch (err) {
      setError(err.message || 'Payment execution initiation failed');
    } finally {
      setExecuting(false);
    }
  };

  const handleConfirmCapture = async (orderIdOverride) => {
    const orderId = orderIdOverride || approvalState?.orderId;
    if (!orderId || !verdict) return;

    setCapturing(true);
    setCaptureError(null);
    try {
      const capRes = await captureIntent(verdict.id, orderId);
      const debitedBucket = verdict.source_bucket || verdict.recommended_bucket || 'freedom';
      const settledCents = verdict.amount || verdict.action_card?.amount_cents || Math.round(parseFloat(amountStr || '0') * 100) || 0;
      setCaptureSuccess({
        captureId: capRes.paypal_capture_id,
        orderId: orderId,
        bucket: debitedBucket
      });
      showToast({
        type: 'order_success',
        title: 'PayPal Payment Settled',
        message: `Payment of $${(settledCents / 100).toFixed(2)} captured & settled from ${debitedBucket} bucket.`,
        details: `Order: ${orderId} · Capture: ${capRes.paypal_capture_id}`,
        duration: 5000,
      });
      onSuccess?.();
      // Auto-close modal after brief visual confirmation
      setTimeout(() => {
        onClose();
      }, 1500);
    } catch (err) {
      const isUnapproved = err.message?.includes('ORDER_NOT_APPROVED');
      setCaptureError(
        isUnapproved
          ? 'PayPal reports buyer approval is not finished yet. Please log into the PayPal window, review the amount, and click "Continue" / "Agree", then click here to complete.'
          : err.message || 'Capture failed'
      );
    } finally {
      setCapturing(false);
    }
  };

  const handleStageToBatch = async (emailOverride) => {
    if (!verdict) return;
    const finalEmail = emailOverride || batchEmail || (merchant && merchant.includes('@') ? merchant : '');
    if (!finalEmail || !finalEmail.includes('@')) {
      setShowEmailPrompt(true);
      return;
    }
    setStaging(true);
    setError(null);
    try {
      const cents = verdict.amount || verdict.action_card?.amount_cents || Math.round(parseFloat(amountStr || '0') * 100);
      await stageIntentToBatch({
        intent_id: verdict.id,
        recipient_email: finalEmail,
        amount_cents: cents,
        currency: verdict.currency || 'USD',
        category: verdict.category || 'bills',
        source_bucket: verdict.source_bucket === 'vault' ? 'vault' : 'bills',
        note: utterance || `Quick Intent to ${finalEmail}`,
      });
      setStagedSuccess(true);
      setShowEmailPrompt(false);
      showToast({
        type: 'batch_success',
        title: 'Staged in Batch Dispatcher',
        message: `Queued $${(cents / 100).toFixed(2)} for batch execution from isolated ${verdict.source_bucket === 'vault' ? 'Vault' : 'Reserved Bills'} reserve.`,
        details: `Payee: ${finalEmail}`,
        duration: 4500,
      });
      onSuccess?.();
    } catch (err) {
      setError(err.message || 'Failed to stage into Batch Dispatcher');
    } finally {
      setStaging(false);
    }
  };

  const isAccepted = verdict?.verdict === 'accepted' || verdict?.status === 'allowed';
  const isRejected = verdict?.verdict === 'rejected' || verdict?.status === 'denied';

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4 animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-800 rounded-t-3xl sm:rounded-2xl max-w-md w-full p-6 shadow-2xl overflow-hidden max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-emerald-400"></span>
            <h3 className="text-base font-bold text-white">Quick Intent Gateway</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-rose-950/60 border border-rose-800 rounded-xl text-xs text-rose-300 flex items-start gap-2">
            <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
            <span>{error}</span>
          </div>
        )}

        {!verdict ? (
          <form onSubmit={handleEvaluate} className="space-y-4 mt-4">
            {/* Amount input */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Amount ($ USD)
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 font-bold text-lg">$</span>
                <input
                  type="number"
                  step="0.01"
                  required
                  value={amountStr}
                  onChange={(e) => setAmountStr(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-8 pr-4 py-3 text-white text-xl font-bold focus:outline-none focus:border-emerald-500 transition-colors"
                  placeholder="0.00"
                />
              </div>
            </div>

            {/* Utterance / Intent */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Why are you spending?
              </label>
              <textarea
                required
                rows={2}
                value={utterance}
                onChange={(e) => setUtterance(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-sm text-white focus:outline-none focus:border-emerald-500 transition-colors resize-none"
                placeholder="e.g. Buying groceries, takeout, gift for family, or urgent ER visit..."
              />
            </div>

            {/* Merchant */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Merchant (Optional)
              </label>
              <input
                type="text"
                value={merchant}
                onChange={(e) => setMerchant(e.target.value)}
                className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2 text-sm text-white focus:outline-none focus:border-emerald-500 transition-colors"
                placeholder="e.g. Safeway, DoorDash, City Hospital"
              />
            </div>

            {/* Submit check button */}
            <button
              type="submit"
              disabled={loading}
              className="w-full py-3.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-50"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Unified Agent Validating...</span>
                </>
              ) : (
                <>
                  <span>Validate Quick Intent</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        ) : (
          /* Verdict View */
          <div className="space-y-4 mt-4 animate-in fade-in">
            <div
              className={`p-4 rounded-xl border ${
                isAccepted
                  ? 'bg-emerald-950/40 border-emerald-800'
                  : isRejected
                  ? 'bg-rose-950/50 border-rose-800'
                  : 'bg-amber-950/40 border-amber-800'
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  {isAccepted ? (
                    <ShieldCheck className="w-5 h-5 text-emerald-400" />
                  ) : (
                    <ShieldAlert className={`w-5 h-5 ${isRejected ? 'text-rose-400' : 'text-amber-400'}`} />
                  )}
                  <span
                    className={`text-sm font-bold uppercase tracking-wider ${
                      isAccepted
                        ? 'text-emerald-300'
                        : isRejected
                        ? 'text-rose-300'
                        : 'text-amber-300'
                    }`}
                  >
                    {isAccepted
                      ? 'Intent Accepted'
                      : isRejected
                      ? 'Intent Rejected'
                      : 'Refer to Coach / Override'}
                  </span>
                </div>

                {verdict.short_tag && (
                  <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800 text-[11px] font-semibold">
                    <Tag className="w-3 h-3 text-indigo-400" />#{verdict.short_tag}
                  </span>
                )}
              </div>

              <p className="text-xs text-slate-300 mt-2 leading-relaxed">{verdict.rationale}</p>

              {verdict.is_emergency && (
                <div className="mt-2.5 px-2.5 py-1.5 rounded-lg bg-amber-500/10 border border-amber-500/30 text-[11px] text-amber-300 flex items-center gap-1.5 font-semibold">
                  <Zap className="w-3.5 h-3.5 text-amber-400 shrink-0" />
                  <span>Genuine emergency detected — 0-second zero-delay unlock eligible!</span>
                </div>
              )}

              <div className="mt-3 pt-3 border-t border-slate-800/80 flex flex-wrap gap-2 text-xs">
                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 capitalize">
                  Category: <strong>{verdict.category}</strong>
                </span>
                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300 capitalize">
                  Bucket: <strong>{verdict.source_bucket}</strong>
                </span>
                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                  Confidence: <strong>{Math.round((verdict.confidence || 0.95) * 100)}%</strong>
                </span>
              </div>
            </div>

            {captureSuccess ? (
              <div className="p-4 rounded-xl bg-emerald-950/70 border border-emerald-800 text-emerald-200 flex flex-col gap-2.5 animate-in fade-in">
                <div className="flex items-center gap-2 text-sm font-bold text-emerald-300">
                  <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  <span>PayPal Sandbox Payment Captured &amp; Settled!</span>
                </div>
                <div className="space-y-1 text-xs text-slate-300">
                  <p>• PayPal Capture ID: <strong className="text-white font-mono">{captureSuccess.captureId}</strong></p>
                  <p>• PayPal Order ID: <strong className="text-white font-mono">{captureSuccess.orderId}</strong></p>
                  <p>• Bucket Debited: <strong className="text-white uppercase">{captureSuccess.bucket}</strong></p>
                  <p>• Double-Entry Ledger: <span className="text-emerald-300 font-semibold">Posted &amp; Reconciled</span></p>
                </div>
                <button
                  type="button"
                  onClick={onClose}
                  className="mt-2 w-full py-2.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold rounded-xl text-xs transition-colors shadow"
                >
                  Done
                </button>
              </div>
            ) : approvalState ? (
              <div className="p-4 rounded-xl bg-slate-950/90 border border-amber-500/40 space-y-3.5 animate-in fade-in">
                <div className="flex items-center gap-2">
                  <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
                    <ExternalLink className="w-4 h-4" />
                  </div>
                  <div>
                    <h4 className="text-sm font-bold text-white">Approve in PayPal Sandbox</h4>
                    <p className="text-[11px] text-amber-300">Checkout opened in another window</p>
                  </div>
                </div>

                <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-1.5 text-xs text-slate-300">
                  <p className="font-semibold text-white">Interactive Sandbox Steps:</p>
                  <ol className="list-decimal pl-4 space-y-1 text-slate-400 text-[11px]">
                    <li>Log into PayPal using your <strong>Sandbox Personal Buyer</strong> credentials.</li>
                    <li>Review <strong>${((verdict.amount || 0) / 100).toFixed(2)}</strong> and click <strong>"Continue" / "Agree"</strong>.</li>
                    <li>Click <strong>"Complete &amp; Settle"</strong> below (or auto-detect will capture).</li>
                  </ol>
                </div>

                {captureError && (
                  <div className="p-2.5 rounded-lg bg-rose-950/60 border border-rose-800 text-xs text-rose-300 flex items-start gap-2">
                    <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                    <span className="leading-relaxed">{captureError}</span>
                  </div>
                )}

                <div className="space-y-2 pt-1">
                  <button
                    type="button"
                    onClick={() => handleConfirmCapture()}
                    disabled={capturing}
                    className="w-full py-3 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-extrabold rounded-xl flex items-center justify-center gap-2 shadow-lg transition-all disabled:opacity-50 text-xs"
                  >
                    {capturing ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Verifying Completion with PayPal...</span>
                      </>
                    ) : (
                      <>
                        <CheckCircle2 className="w-4 h-4" />
                        <span>I've Approved on PayPal — Complete &amp; Settle</span>
                      </>
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={() => window.open(approvalState.approvalUrl, '_blank', 'noopener,noreferrer')}
                    className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium rounded-lg text-xs flex items-center justify-center gap-1.5 transition-colors"
                  >
                    <ExternalLink className="w-3.5 h-3.5" />
                    <span>Reopen PayPal Checkout Window</span>
                  </button>
                </div>
              </div>
            ) : stagedSuccess ? (
              <div className="p-4 rounded-xl bg-sky-950/70 border border-sky-800 text-sky-200 flex flex-col gap-2.5 animate-in fade-in">
                <div className="flex items-center gap-2 text-sm font-bold text-sky-300">
                  <CheckCircle2 className="w-5 h-5 text-sky-400" />
                  <span>Staged in The Trinity Batch Dispatcher!</span>
                </div>
                <p className="text-xs text-slate-300">
                  This obligation of <strong>${(((verdict.amount || verdict.action_card?.amount_cents || Math.round(parseFloat(amountStr || '0') * 100)) || 0) / 100).toFixed(2)}</strong> is queued as <em>pending approval</em> under your isolated {verdict.source_bucket === 'vault' ? 'Vault' : 'Reserved Bills'} reserve.
                </p>
                {onOpenBatchDispatcher && (
                  <button
                    type="button"
                    onClick={() => {
                      onClose();
                      onOpenBatchDispatcher();
                    }}
                    className="w-full py-2.5 bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold rounded-xl flex items-center justify-center gap-2 text-xs transition-colors shadow"
                  >
                    <Layers className="w-4 h-4" />
                    <span>Open Batch Dispatcher ({verdict.source_bucket.toUpperCase()})</span>
                  </button>
                )}
              </div>
            ) : isAccepted ? (
              <div className="space-y-2.5">
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                  <button
                    onClick={handleExecutePayPal}
                    disabled={executing || staging}
                    className="py-3 bg-gradient-to-r from-amber-400 to-amber-500 hover:from-amber-300 hover:to-amber-400 text-slate-950 font-extrabold rounded-xl flex items-center justify-center gap-1.5 shadow-lg transition-all disabled:opacity-50 text-xs"
                  >
                    {executing ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Starting PayPal Checkout...</span>
                      </>
                    ) : (
                      <>
                        <span>Pay with PayPal Sandbox</span>
                        <ExternalLink className="w-3.5 h-3.5" />
                      </>
                    )}
                  </button>

                  <button
                    type="button"
                    onClick={() => {
                      if (!merchant.includes('@') && !batchEmail) {
                        setShowEmailPrompt(true);
                      } else {
                        handleStageToBatch();
                      }
                    }}
                    disabled={executing || staging}
                    className="py-3 bg-sky-600 hover:bg-sky-500 text-white font-bold rounded-xl flex items-center justify-center gap-1.5 shadow-lg transition-all disabled:opacity-50 text-xs"
                  >
                    {staging ? (
                      <>
                        <Loader2 className="w-4 h-4 animate-spin" />
                        <span>Staging...</span>
                      </>
                    ) : (
                      <>
                        <Layers className="w-3.5 h-3.5" />
                        <span>Add to Batch Queue</span>
                      </>
                    )}
                  </button>
                </div>

                {showEmailPrompt && (
                  <div className="p-3 bg-slate-950/90 border border-slate-700 rounded-xl space-y-2 text-xs animate-in fade-in">
                    <label className="text-[11px] font-semibold text-slate-300 block">
                      PayPal Payee Email for Batch Payout:
                    </label>
                    <div className="flex gap-2">
                      <input
                        type="email"
                        required
                        value={batchEmail}
                        onChange={(e) => setBatchEmail(e.target.value)}
                        placeholder="payee@sandbox.paypal.com"
                        className="flex-1 bg-slate-900 border border-slate-700 rounded-lg px-2.5 py-1.5 text-xs text-white focus:outline-none focus:border-sky-500"
                      />
                      <button
                        type="button"
                        onClick={() => handleStageToBatch(batchEmail)}
                        disabled={!batchEmail.includes('@') || staging}
                        className="px-3 py-1.5 bg-sky-500 hover:bg-sky-400 text-slate-950 font-bold rounded-lg text-xs disabled:opacity-50"
                      >
                        Confirm Stage
                      </button>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="space-y-2.5">
                {/* Refer to Coach for Conversational Reasoning */}
                {onAskCoach && (
                  <button
                    onClick={() => {
                      const q = `Help me reason through spending $${parseFloat(amountStr || '0').toFixed(2)} for "${utterance}" (${verdict.short_tag || verdict.category}).`;
                      onClose();
                      onAskCoach(q);
                    }}
                    className="w-full py-3 bg-purple-600 hover:bg-purple-500 text-white font-bold rounded-xl flex items-center justify-center gap-2 shadow-lg transition-colors"
                  >
                    <Sparkles className="w-4 h-4" />
                    <span>Reason with Trinity Coach</span>
                  </button>
                )}

                {!isRejected && (
                  <>
                    <button
                      onClick={() => {
                        onClose();
                        onOpenOverride?.(verdict.id);
                      }}
                      className={`w-full py-3 font-bold rounded-xl flex items-center justify-center gap-2 shadow-lg transition-colors ${
                        verdict.is_emergency
                          ? 'bg-amber-500 hover:bg-amber-400 text-slate-950'
                          : 'bg-rose-600 hover:bg-rose-500 text-white'
                      }`}
                    >
                      {verdict.is_emergency ? <Zap className="w-4 h-4" /> : <Lock className="w-4 h-4" />}
                      <span>
                        {verdict.is_emergency
                          ? 'Instant Emergency Override (0s Delay)'
                          : 'Open Escape Window (Override)'}
                      </span>
                    </button>
                    <p className="text-[11px] text-center text-slate-400">
                      {verdict.is_emergency
                        ? 'Valid emergencies bypass the 200-char wall & 3-minute cooldown.'
                        : 'Non-emergency splurges require a 200-character reflection + 3-minute cooldown.'}
                    </p>
                  </>
                )}
              </div>
            )}

            <button
              onClick={() => setVerdict(null)}
              className="w-full py-2 text-xs text-slate-400 hover:text-white transition-colors text-center"
            >
              Test another intent
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
