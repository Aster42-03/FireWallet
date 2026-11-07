import React, { useState } from 'react';
import { X, ShieldCheck, ShieldAlert, Lock, ArrowRight, Loader2, ExternalLink } from 'lucide-react';
import { submitIntent, executeIntent, captureIntent } from '../../shared/api';

export default function QuickIntentModal({ isOpen, onClose, onOpenOverride, onSuccess }) {
  const [amountStr, setAmountStr] = useState('24.00');
  const [utterance, setUtterance] = useState('Buying groceries at Trader Joe\'s');
  const [merchant, setMerchant] = useState('Trader Joe\'s');
  
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
      
      // Simulate/Trigger PayPal approval window
      const approvalUrl = execRes.approval_url || `https://www.sandbox.paypal.com/checkoutnow?token=${execRes.paypal_order_id}`;
      
      // In sandbox demo, settle order
      await captureIntent(verdict.id, execRes.paypal_order_id);
      
      alert(`PayPal Sandbox Payment Captured Successfully!\nOrder ID: ${execRes.paypal_order_id}\nBucket Settled: ${verdict.source_bucket}`);
      onSuccess?.();
      onClose();
    } catch (err) {
      setError(err.message || 'Payment execution failed');
    } finally {
      setExecuting(false);
    }
  };

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
                placeholder="e.g. Buying groceries vs Ordering late-night takeout..."
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
                placeholder="e.g. Safeway, DoorDash, Landlord"
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
                  <span>Intent Agent Parsing...</span>
                </>
              ) : (
                <>
                  <span>Check with Firewall</span>
                  <ArrowRight className="w-4 h-4" />
                </>
              )}
            </button>
          </form>
        ) : (
          /* Verdict View */
          <div className="space-y-4 mt-4 animate-in fade-in">
            <div className={`p-4 rounded-xl border ${verdict.status === 'allowed' ? 'bg-emerald-950/40 border-emerald-800' : 'bg-rose-950/40 border-rose-800'}`}>
              <div className="flex items-center gap-2">
                {verdict.status === 'allowed' ? (
                  <ShieldCheck className="w-5 h-5 text-emerald-400" />
                ) : (
                  <ShieldAlert className="w-5 h-5 text-rose-400" />
                )}
                <span className={`text-sm font-bold uppercase tracking-wider ${verdict.status === 'allowed' ? 'text-emerald-300' : 'text-rose-300'}`}>
                  {verdict.status === 'allowed' ? 'Intent Authorized' : 'Blocked by Firewall'}
                </span>
              </div>

              <p className="text-xs text-slate-300 mt-2 leading-relaxed">
                {verdict.rationale}
              </p>

              <div className="mt-3 pt-3 border-t border-slate-800/80 flex flex-wrap gap-2 text-xs">
                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                  Category: <strong>{verdict.category}</strong>
                </span>
                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                  Target: <strong>{verdict.source_bucket}</strong>
                </span>
                <span className="px-2 py-0.5 rounded bg-slate-800 text-slate-300">
                  Confidence: <strong>{Math.round((verdict.confidence || 0.95) * 100)}%</strong>
                </span>
              </div>
            </div>

            {verdict.status === 'allowed' ? (
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
                    <span>Pay with PayPal Sandbox</span>
                    <ExternalLink className="w-4 h-4" />
                  </>
                )}
              </button>
            ) : (
              <div className="space-y-2">
                <button
                  onClick={() => {
                    onClose();
                    onOpenOverride?.(verdict.id);
                  }}
                  className="w-full py-3 bg-rose-600 hover:bg-rose-500 text-white font-bold rounded-xl flex items-center justify-center gap-2 shadow-lg transition-colors"
                >
                  <Lock className="w-4 h-4" />
                  <span>Open Escape Window (Override)</span>
                </button>
                <p className="text-[11px] text-center text-slate-400">
                  Friction is required: 200-character confession + 3-minute cooldown.
                </p>
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
