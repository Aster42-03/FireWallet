import React, { useState, useEffect } from 'react';
import { X, Lock, AlertTriangle, Clock, CheckCircle2, Loader2, Zap, Tag } from 'lucide-react';
import { submitOverride, checkCooldown, executeIntent, captureIntent } from '../../shared/api';

export default function EscapeWindowModal({ isOpen, onClose, intentId, onSuccess }) {
  const [confession, setConfession] = useState('');
  const [isEmergencyMode, setIsEmergencyMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [overrideData, setOverrideData] = useState(null);
  const [secondsLeft, setSecondsLeft] = useState(180);
  const [readyToExecute, setReadyToExecute] = useState(false);
  const [error, setError] = useState(null);

  const minChars = isEmergencyMode ? 10 : 200;

  useEffect(() => {
    if (!isOpen) {
      setConfession('');
      setIsEmergencyMode(false);
      setOverrideData(null);
      setSecondsLeft(180);
      setReadyToExecute(false);
      setError(null);
    }
  }, [isOpen]);

  useEffect(() => {
    let timer;
    if (overrideData && secondsLeft > 0) {
      timer = setInterval(() => {
        setSecondsLeft(prev => {
          if (prev <= 1) {
            clearInterval(timer);
            setReadyToExecute(true);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [overrideData, secondsLeft]);

  if (!isOpen) return null;

  const handleSubmitConfession = async (e) => {
    e.preventDefault();
    if (confession.trim().length < minChars) {
      setError(
        isEmergencyMode
          ? 'Please briefly describe the medical/safety emergency (at least 10 characters).'
          : `Your confession must be at least ${minChars} characters to ensure deliberate reflection.`
      );
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await submitOverride(intentId, confession);
      setOverrideData(res);
      const cd = res.cooldown_seconds ?? 180;
      setSecondsLeft(cd);
      if (cd <= 0 || res.status === 'approved' || res.is_emergency) {
        setReadyToExecute(true);
      }
    } catch (err) {
      setError(err.message || 'Failed to initiate Escape Window override');
    } finally {
      setLoading(false);
    }
  };

  const handleUnlockAndExecute = async () => {
    setLoading(true);
    setError(null);
    try {
      await checkCooldown(overrideData.id);
      const execRes = await executeIntent(intentId);
      await captureIntent(intentId, execRes.paypal_order_id);
      alert(
        `Override Approved & Settled!\nTag: #${overrideData.short_tag || 'override'}\nOrder ID: ${execRes.paypal_order_id}`
      );
      onSuccess?.();
      onClose();
    } catch (err) {
      setError(err.message || 'Execution failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in">
      <div className="bg-slate-900 border border-rose-900/50 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative overflow-hidden">
        {/* Top glow */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-rose-500 to-amber-500"></div>

        {/* Header */}
        <div className="flex items-start justify-between pb-4 border-b border-slate-800">
          <div>
            <div className="flex items-center gap-2 text-rose-400 font-bold text-sm">
              <AlertTriangle className="w-4 h-4" />
              <span>THE ESCAPE WINDOW</span>
            </div>
            <h3 className="text-xl font-extrabold text-white mt-1">
              {isEmergencyMode ? 'Emergency Zero-Delay Verification' : 'Friction-Based Override'}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-rose-950/80 border border-rose-800 rounded-xl text-xs text-rose-300">
            {error}
          </div>
        )}

        {!overrideData ? (
          <form onSubmit={handleSubmitConfession} className="space-y-4 mt-4">
            {/* Emergency Mode Switcher */}
            <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs">
              <div className="flex items-center gap-2">
                <Zap className={`w-4 h-4 ${isEmergencyMode ? 'text-amber-400' : 'text-slate-500'}`} />
                <div>
                  <div className="font-bold text-slate-200">Valid Medical / Safety Emergency?</div>
                  <div className="text-[11px] text-slate-400">
                    Verified ER, urgent care, stranded, or shutoff needs get 0s delay.
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setIsEmergencyMode(prev => !prev);
                  setError(null);
                }}
                className={`px-3 py-1.5 rounded-lg font-bold transition-colors ${
                  isEmergencyMode
                    ? 'bg-amber-500 text-slate-950'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                }`}
              >
                {isEmergencyMode ? 'Emergency On' : 'Standard'}
              </button>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              {isEmergencyMode
                ? 'Describe the urgent situation below. Our backend guardrail verifies genuine medical, safety, or critical emergencies and unlocks Bank funds with zero cooldown.'
                : 'Your Trinity rules exist to protect your rent and daily allowance. To raid your Bank foundation for a non-emergency purchase, write a 200-character reflection.'}
            </p>

            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>
                  {isEmergencyMode ? 'Emergency Reason' : 'Written Reflection'} ({confession.trim().length}/{minChars} chars)
                </span>
                <span className={confession.trim().length >= minChars ? 'text-emerald-400' : 'text-amber-400'}>
                  {confession.trim().length >= minChars
                    ? 'Requirement met'
                    : `${minChars - confession.trim().length} chars needed`}
                </span>
              </div>
              <textarea
                required
                rows={4}
                value={confession}
                onChange={(e) => setConfession(e.target.value)}
                placeholder={
                  isEmergencyMode
                    ? 'e.g. At urgent care clinic needing emergency prescription & x-ray copay...'
                    : 'I understand my Freedom envelope is depleted. I am choosing to raid my Bank foundation for this purchase because...'
                }
                className="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-sm text-white focus:outline-none focus:border-rose-500 transition-colors resize-none"
              />
            </div>

            <button
              type="submit"
              disabled={loading || confession.trim().length < minChars}
              className={`w-full py-3.5 disabled:opacity-40 font-bold rounded-xl flex items-center justify-center gap-2 transition-all ${
                isEmergencyMode
                  ? 'bg-amber-500 hover:bg-amber-400 text-slate-950'
                  : 'bg-rose-600 hover:bg-rose-500 text-white'
              }`}
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Verifying Override...</span>
                </>
              ) : isEmergencyMode ? (
                <>
                  <Zap className="w-4 h-4" />
                  <span>Verify Emergency (0s Delay)</span>
                </>
              ) : (
                <>
                  <Lock className="w-4 h-4" />
                  <span>Begin 3-Minute Cooldown</span>
                </>
              )}
            </button>
          </form>
        ) : (
          /* Cooldown / Instant Emergency Unlock Phase */
          <div className="space-y-5 mt-4 text-center">
            <div
              className={`w-16 h-16 rounded-full flex items-center justify-center mx-auto border ${
                overrideData.is_emergency
                  ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-400'
                  : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
              }`}
            >
              {overrideData.is_emergency ? (
                <Zap className="w-8 h-8" />
              ) : (
                <Clock className="w-8 h-8 animate-pulse" />
              )}
            </div>

            <div>
              <h4 className="text-lg font-bold text-white">
                {overrideData.is_emergency
                  ? 'Emergency Verified — Zero Cooldown!'
                  : 'Server-Enforced Cooldown Active'}
              </h4>
              <p className="text-xs text-slate-400 mt-1">
                {overrideData.is_emergency
                  ? 'No waiting period applied. Your Bank Foundation is unlocked for immediate PayPal settlement.'
                  : 'Take a deep breath. Cooling off prevents 92% of regretful late-night purchases.'}
              </p>
              {overrideData.short_tag && (
                <div className="mt-2 inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800 text-[11px] font-semibold">
                  <Tag className="w-3 h-3 text-indigo-400" />
                  Recorded RAG Tag: #{overrideData.short_tag}
                </div>
              )}
            </div>

            <div className="py-4 bg-slate-950 border border-slate-800 rounded-2xl">
              <span
                className={`text-4xl font-mono font-extrabold ${
                  overrideData.is_emergency ? 'text-emerald-400' : 'text-amber-400'
                }`}
              >
                {Math.floor(secondsLeft / 60)}:{(secondsLeft % 60).toString().padStart(2, '0')}
              </span>
              <p className="text-[11px] text-slate-500 mt-1 uppercase tracking-wider font-semibold">
                {overrideData.is_emergency ? 'Zero Delay Applied' : 'Time Remaining'}
              </p>
            </div>

            {readyToExecute ? (
              <button
                onClick={handleUnlockAndExecute}
                disabled={loading}
                className="w-full py-3.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold rounded-xl flex items-center justify-center gap-2 transition-all shadow-lg disabled:opacity-50"
              >
                {loading ? (
                  <>
                    <Loader2 className="w-5 h-5 animate-spin" />
                    <span>Executing PayPal Checkout...</span>
                  </>
                ) : (
                  <>
                    <CheckCircle2 className="w-5 h-5" />
                    <span>Confirm & Pay via PayPal Now</span>
                  </>
                )}
              </button>
            ) : (
              <p className="text-xs text-slate-400 italic">
                Execution requests will return HTTP 409 until cooldown timer expires.
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
