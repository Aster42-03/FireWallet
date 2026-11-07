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
  Zap
} from 'lucide-react';
import { submitIntent, executeIntent, captureIntent } from '../../shared/api';

export default function QuickIntentModal({
  isOpen,
  onClose,
  onOpenOverride,
  onAskCoach,
  onSuccess
}) {
  const [amountStr, setAmountStr] = useState('24.00');
  const [utterance, setUtterance] = useState("Buying groceries at Trader Joe's");
  const [merchant, setMerchant] = useState("Trader Joe's");

  const [loading, setLoading] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [verdict, setVerdict] = useState(null);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const handleEvaluate = async (e) => {
    e.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const cents = Math.round(parseFloat(amountStr || '0') * 100);
      if (isNaN(cents) || cents <= 0) {
        throw new Error('Please enter a valid positive dollar amount.');
      }
      const res = await submitIntent(utterance, cents, merchant);
      setVerdict(res);
    } catch (err) {
      setError(err.message || 'Evaluation failed');
    } finally {
      setLoading(false);
    }
  };

  const handleExecutePayPal = async () => {
    if (!verdict) return;
    setExecuting(true);
    setError(null);
    try {
      const execRes = await executeIntent(verdict.id);
      
      // If a real approval URL is returned, open it for user authorization
      if (execRes.approval_url && !execRes.approval_url.includes('ORDER-MOCK')) {
        window.open(execRes.approval_url, '_blank', 'noopener,noreferrer');
      }

      await captureIntent(verdict.id, execRes.paypal_order_id);

      alert(
        `PayPal Sandbox Payment Captured Successfully!\n\n` +
        `• PayPal Order ID: ${execRes.paypal_order_id}\n` +
        `• Bucket Debited: ${verdict.source_bucket.toUpperCase()}\n` +
        `• Tag: #${verdict.short_tag || verdict.category}`
      );
      onSuccess?.();
      onClose();
    } catch (err) {
      setError(err.message || 'Payment execution failed');
    } finally {
      setExecuting(false);
    }
  };

  const isAccepted = verdict?.verdict === 'accepted' || verdict?.status === 'allowed';
  const isRejected = verdict?.verdict === 'rejected' || verdict?.status === 'denied';

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

            {isAccepted ? (
              <button
                onClick={handleExecutePayPal}
                disabled={executing}
                className="w-full py-3.5 bg-gradient-to-r from-amber-400 to-amber-500 hover:from-amber-300 hover:to-amber-400 text-slate-950 font-extrabold rounded-xl flex items-center justify-center gap-2 shadow-lg transition-all disabled:opacity-50"
              >
                {executing ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span>Executing PayPal Orders v2...</span>
                  </>
                ) : (
                  <>
                    <span>{verdict.action_card?.label || 'Pay with PayPal Sandbox'}</span>
                    <ExternalLink className="w-4 h-4" />
                  </>
                )}
              </button>
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
