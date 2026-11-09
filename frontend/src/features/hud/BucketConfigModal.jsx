import React, { useState, useEffect } from 'react';
import { X, Sliders, Loader2, ShieldCheck, CheckCircle2 } from 'lucide-react';
import { fetchPolicy, updatePolicy } from '../../shared/api';

export default function BucketConfigModal({ isOpen, onClose, onSuccess }) {
  const [dailyDollars, setDailyDollars] = useState('40.00');
  const [freedomDollars, setFreedomDollars] = useState('150.00');
  const [billsDollars, setBillsDollars] = useState('1200.00');
  const [vaultPercent, setVaultPercent] = useState('20');
  const [cooldownSeconds, setCooldownSeconds] = useState('180');
  const [minChars, setMinChars] = useState('200');

  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState(null);
  const [savedToast, setSavedToast] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setError(null);
    setSavedToast(false);
    setLoading(true);
    fetchPolicy()
      .then((pol) => {
        if (pol.daily_amount !== undefined) {
          setDailyDollars((pol.daily_amount / 100).toFixed(2));
        }
        if (pol.freedom_monthly_amount !== undefined) {
          setFreedomDollars((pol.freedom_monthly_amount / 100).toFixed(2));
        }
        if (pol.bills_monthly_amount !== undefined && pol.bills_monthly_amount !== null) {
          setBillsDollars((pol.bills_monthly_amount / 100).toFixed(2));
        }
        if (pol.vault_skim_bps !== undefined) {
          setVaultPercent(String(Math.round(pol.vault_skim_bps / 100)));
        }
        if (pol.override_cooldown_seconds !== undefined) {
          setCooldownSeconds(String(pol.override_cooldown_seconds));
        }
        if (pol.override_min_chars !== undefined) {
          setMinChars(String(pol.override_min_chars));
        }
      })
      .catch((err) => {
        setError(err.message || 'Could not load current bucket settings');
      })
      .finally(() => {
        setLoading(false);
      });
  }, [isOpen]);

  if (!isOpen) return null;

  const handleSave = async (e) => {
    e.preventDefault();
    setError(null);
    setSaving(true);
    try {
      const dailyCents = Math.max(0, Math.round(parseFloat(dailyDollars || '0') * 100));
      const freedomCents = Math.max(0, Math.round(parseFloat(freedomDollars || '0') * 100));
      const billsCents = Math.max(0, Math.round(parseFloat(billsDollars || '0') * 100));
      const vaultPctNum = Math.min(100, Math.max(0, parseFloat(vaultPercent || '0')));
      const vaultBps = Math.round(vaultPctNum * 100);
      const cooldown = Math.max(10, parseInt(cooldownSeconds || '180', 10));
      const chars = Math.max(50, parseInt(minChars || '200', 10));

      await updatePolicy({
        daily_amount: dailyCents,
        freedom_monthly_amount: freedomCents,
        bills_monthly_amount: billsCents,
        vault_skim_bps: vaultBps,
        override_cooldown_seconds: cooldown,
        override_min_chars: chars
      });

      setSavedToast(true);
      onSuccess?.();
      setTimeout(() => {
        onClose();
      }, 600);
    } catch (err) {
      setError(err.message || 'Failed to save bucket configuration');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex items-end sm:items-center justify-center p-0 sm:p-4 animate-in fade-in duration-200">
      <div className="bg-slate-900 border border-slate-800 rounded-t-3xl sm:rounded-2xl max-w-md w-full p-6 shadow-2xl overflow-hidden max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between pb-3 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Sliders className="w-4 h-4 text-emerald-400" />
            <h3 className="text-base font-bold text-white">Configure Envelopes</h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <p className="text-xs text-slate-400 mt-3 leading-relaxed">
          Customize your envelope rules. When your PayPal balance syncs or updates, funds are automatically distributed according to these targets and the remainder stays protected in Bank Foundation.
        </p>

        {error && (
          <div className="mt-4 p-3 bg-rose-950/60 border border-rose-800 rounded-xl text-xs text-rose-300">
            {error}
          </div>
        )}

        {savedToast && (
          <div className="mt-4 p-3 bg-emerald-950/60 border border-emerald-800 rounded-xl text-xs text-emerald-300 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>Envelope configuration saved and balances reallocated!</span>
          </div>
        )}

        {loading ? (
          <div className="py-10 flex items-center justify-center gap-2 text-xs text-slate-400">
            <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
            <span>Loading bucket configuration...</span>
          </div>
        ) : (
          <form onSubmit={handleSave} className="space-y-4 mt-4">
            {/* Daily ($/day) */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Daily ($/day)
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 font-bold text-sm">$</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  required
                  value={dailyDollars}
                  onChange={(e) => setDailyDollars(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-8 pr-4 py-2.5 text-white text-sm font-bold focus:outline-none focus:border-emerald-500 transition-colors"
                />
              </div>
            </div>

            {/* Freedom ($/month) */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Freedom ($/month)
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 font-bold text-sm">$</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  required
                  value={freedomDollars}
                  onChange={(e) => setFreedomDollars(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-8 pr-4 py-2.5 text-white text-sm font-bold focus:outline-none focus:border-emerald-500 transition-colors"
                />
              </div>
            </div>

            {/* Reserved Bills ($/month) */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Reserved Bills ($/month)
              </label>
              <div className="relative">
                <span className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-400 font-bold text-sm">$</span>
                <input
                  type="number"
                  step="0.01"
                  min="0"
                  required
                  value={billsDollars}
                  onChange={(e) => setBillsDollars(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl pl-8 pr-4 py-2.5 text-white text-sm font-bold focus:outline-none focus:border-emerald-500 transition-colors"
                  placeholder="1200.00"
                />
              </div>
              <p className="text-[10px] text-slate-500 mt-1">Earmarked from Bank Foundation for contractual obligations (rent, utilities).</p>
            </div>

            {/* Vault (%) */}
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-1">
                Vault (%)
              </label>
              <div className="relative">
                <input
                  type="number"
                  step="1"
                  min="0"
                  max="100"
                  required
                  value={vaultPercent}
                  onChange={(e) => setVaultPercent(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3.5 py-2.5 text-white text-sm font-bold focus:outline-none focus:border-emerald-500 transition-colors"
                />
                <span className="absolute right-3.5 top-1/2 -translate-y-1/2 text-slate-400 font-bold text-sm">%</span>
              </div>
            </div>

            {/* Emergency Override Cooldown & Minimum Characters */}
            <div className="grid grid-cols-2 gap-3 pt-1">
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  Override Cooldown (s)
                </label>
                <input
                  type="number"
                  min="10"
                  required
                  value={cooldownSeconds}
                  onChange={(e) => setCooldownSeconds(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white text-xs font-semibold focus:outline-none focus:border-emerald-500 transition-colors"
                />
              </div>
              <div>
                <label className="block text-[11px] font-semibold text-slate-400 uppercase tracking-wider mb-1">
                  Confession Min Chars
                </label>
                <input
                  type="number"
                  min="50"
                  required
                  value={minChars}
                  onChange={(e) => setMinChars(e.target.value)}
                  className="w-full bg-slate-950 border border-slate-700 rounded-xl px-3 py-2 text-white text-xs font-semibold focus:outline-none focus:border-emerald-500 transition-colors"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={saving}
              className="w-full py-3 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold rounded-xl flex items-center justify-center gap-2 transition-colors disabled:opacity-50 mt-2"
            >
              {saving ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Saving &amp; Reallocating...</span>
                </>
              ) : (
                <>
                  <ShieldCheck className="w-4 h-4" />
                  <span>Save &amp; Sync Envelopes</span>
                </>
              )}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
