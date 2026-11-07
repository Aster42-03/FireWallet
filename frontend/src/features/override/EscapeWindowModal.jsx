import React, { useState, useEffect } from 'react';
import { X, Lock, AlertTriangle, Clock, CheckCircle2, Loader2 } from 'lucide-react';
import { submitOverride, checkCooldown, executeIntent } from '../../shared/api';

export default function EscapeWindowModal({ isOpen, onClose, intentId, onSuccess }) {
  const [confession, setConfession] = useState('');
  const [loading, setLoading] = useState(false);
  const [overrideData, setOverrideData] = useState(null);
  const [secondsLeft, setSecondsLeft] = useState(180);
  const [readyToExecute, setReadyToExecute] = useState(false);
  const [error, setError] = useState(null);

  const minChars = 200;

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
    if (confession.length < minChars) {
      setError(`Your confession must be at least ${minChars} characters to ensure deliberate reflection.`);
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await submitOverride(intentId, confession);
      setOverrideData(res);
      setSecondsLeft(res.cooldown_seconds || 180);
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
      await executeIntent(intentId);
      alert('Override Approved! PayPal transaction initiated from Bank foundation.');
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
            <h3 className="text-xl font-extrabold text-white mt-1">Friction-Based Override</h3>
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
            <p className="text-xs text-slate-300 leading-relaxed">
              Your Trinity rules exist to protect your rent and daily allowance. To raid your Bank foundation or spend beyond your Freedom envelope, you must write a reflection explaining why this impulse cannot wait.
            </p>

            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>Written Reflection ({confession.length}/{minChars} characters)</span>
                <span className={confession.length >= minChars ? 'text-emerald-400' : 'text-amber-400'}>
                  {confession.length >= minChars ? 'Requirement met' : `${minChars - confession.length} chars needed`}
                </span>
              </div>
              <textarea
                required
                rows={5}
                value={confession}
                onChange={(e) => setConfession(e.target.value)}
                placeholder="I understand my Freedom envelope is depleted. I am choosing to raid my Bank foundation for this purchase because..."
                className="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-sm text-white focus:outline-none focus:border-rose-500 transition-colors resize-none"
              />
            </div>

            <button
              type="submit"
              disabled={loading || confession.length < minChars}
              className="w-full py-3.5 bg-rose-600 hover:bg-rose-500 disabled:opacity-40 text-white font-bold rounded-xl flex items-center justify-center gap-2 transition-all"
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Recording Confession...</span>
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
          /* Cooldown Timer Phase */
          <div className="space-y-5 mt-4 text-center">
            <div className="w-16 h-16 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center mx-auto text-amber-400">
              <Clock className="w-8 h-8 animate-pulse" />
            </div>

            <div>
              <h4 className="text-lg font-bold text-white">Server-Enforced Cooldown Active</h4>
              <p className="text-xs text-slate-400 mt-1">
                Take a deep breath. Cooling off prevents 92% of regretful late-night purchases.
              </p>
            </div>

            <div className="py-4 bg-slate-950 border border-slate-800 rounded-2xl">
              <span className="text-4xl font-mono font-extrabold text-amber-400">
                {Math.floor(secondsLeft / 60)}:{(secondsLeft % 60).toString().padStart(2, '0')}
              </span>
              <p className="text-[11px] text-slate-500 mt-1 uppercase tracking-wider font-semibold">
                Time Remaining
              </p>
            </div>

            {readyToExecute ? (
              <button
                onClick={handleUnlockAndExecute}
                disabled={loading}
                className="w-full py-3.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold rounded-xl flex items-center justify-center gap-2 transition-all shadow-lg"
              >
                <CheckCircle2 className="w-5 h-5" />
                <span>Cooldown Elapsed: Confirm & Execute</span>
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
