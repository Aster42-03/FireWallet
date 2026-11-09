import React, { useState } from 'react';
import {
  Shield,
  Lock,
  Sparkles,
  TrendingUp,
  ArrowUpRight,
  MessageSquareText,
  Zap,
  RefreshCw,
  Sliders
} from 'lucide-react';
import { syncPayPalBalance } from '../../shared/api';
import BatchDispatcherModal from '../bills/BatchDispatcherModal';

export default function MobileHUD({
  buckets,
  stats,
  onOpenIntent,
  onOpenCoach,
  onAskChart,
  onOpenConfig,
  onSyncSuccess,
  onOpenBatchDispatcher
}) {
  const [syncing, setSyncing] = useState(false);
  const [syncNotice, setSyncNotice] = useState(null);
  const [showBatchModal, setShowBatchModal] = useState(false);

  const bank = buckets?.find(b => b.kind === 'bank') || { available: 0 };
  const daily = buckets?.find(b => b.kind === 'daily') || { available: 0 };
  const freedom = buckets?.find(b => b.kind === 'freedom') || { available: 0 };
  const vault = buckets?.find(b => b.kind === 'vault') || { available: 0 };
  const bills = buckets?.find(b => b.kind === 'bills') || { available: 0 };

  const policy = stats?.policy || {};
  const dailyTargetCents = policy.daily_amount ?? 4000;
  const freedomTargetCents = policy.freedom_monthly_amount ?? 15000;
  const vaultPct = Math.round((policy.vault_skim_bps ?? 2000) / 100);

  const formatMoney = (cents) => `$${((cents || 0) / 100).toFixed(2)}`;

  const totalBalanceCents =
    (bank.available || 0) +
    (daily.available || 0) +
    (freedom.available || 0) +
    (vault.available || 0) +
    (bills.available || 0);

  const pieChart = stats?.charts?.find(c => c.id === 'chart_pie_week');
  const categoryItems = pieChart?.data || [];

  const handleSyncPayPal = async () => {
    if (syncing) return;
    setSyncing(true);
    setSyncNotice(null);
    try {
      const res = await syncPayPalBalance();
      const syncedAmt = res?.paypal_balance?.synced_cents ?? totalBalanceCents;
      setSyncNotice(`Synced ${formatMoney(syncedAmt)} from PayPal`);
      onSyncSuccess?.();
      setTimeout(() => setSyncNotice(null), 4000);
    } catch (err) {
      setSyncNotice(err.message || 'Balance sync failed');
    } finally {
      setSyncing(false);
    }
  };

  return (
    <div className="w-full max-w-md md:max-w-4xl lg:max-w-6xl mx-auto px-4 py-6 space-y-4 pb-28 md:pb-12">
      {/* Top Header & PayPal Balance Sync Controls */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <h1 className="text-xl md:text-2xl font-bold tracking-tight text-white">FireWallet</h1>
            <span className="hidden md:inline-block text-[11px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
              Trinity HUD
            </span>
          </div>
          <p className="text-xs text-slate-400 mt-0.5">
            Total Account Balance: <span className="text-slate-200 font-semibold">{formatMoney(totalBalanceCents)}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handleSyncPayPal}
            disabled={syncing}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-emerald-950/70 hover:bg-emerald-900/70 border border-emerald-700/60 rounded-xl text-xs font-semibold text-emerald-300 transition-colors disabled:opacity-50"
            title="Detect and synchronize actual PayPal account balance"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${syncing ? 'animate-spin' : ''}`} />
            <span>{syncing ? 'Syncing...' : 'Sync PayPal'}</span>
          </button>
          <button
            onClick={onOpenConfig}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 hover:bg-slate-800 border border-slate-700 rounded-xl text-xs font-medium text-slate-300 transition-colors"
            title="Configure Daily, Freedom, and Vault envelopes"
          >
            <Sliders className="w-3.5 h-3.5 text-slate-400" />
            <span>Configure</span>
          </button>
        </div>
      </div>

      {syncNotice && (
        <div className="px-3.5 py-2 rounded-xl bg-emerald-950/60 border border-emerald-800/70 text-xs text-emerald-300 flex items-center justify-between">
          <span>{syncNotice}</span>
        </div>
      )}

      {/* Primary Trinity Row: Bank Foundation + Daily Allowance */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 1. Bank Foundation Card */}
        <div className="p-4 md:p-5 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800 shadow-sm relative overflow-hidden flex flex-col justify-between">
          <div>
            <div className="flex items-start justify-between">
              <div>
                <span className="text-xs uppercase tracking-wider font-semibold text-slate-400">Bank Foundation</span>
                <h2 className="text-2xl md:text-3xl font-bold text-white mt-0.5">{formatMoney(bank.available)}</h2>
              </div>
              <span className="px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700 text-[11px] font-medium text-slate-300">
                Protected Remainder
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-xs text-slate-400 mt-2">
              <Lock className="w-3.5 h-3.5 text-amber-400 shrink-0" />
              <span>Direct spend locked &middot; Safeguards cash flow</span>
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] text-slate-500">
            Income destination &amp; allowance source. Raids require Escape Window.
          </div>
        </div>

        {/* 2. Daily Card (with Rollover) */}
        <div className="p-5 rounded-2xl bg-gradient-to-br from-emerald-950/70 via-slate-900 to-slate-950 border border-emerald-800/60 shadow-lg relative flex flex-col justify-between">
          <div>
            <div className="flex items-start justify-between">
              <div>
                <div className="flex items-center gap-1.5">
                  <span className="text-xs uppercase tracking-wider font-semibold text-emerald-400">Daily Living</span>
                  <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 text-[10px] font-medium">
                    {formatMoney(dailyTargetCents)}/day
                  </span>
                </div>
                <h2 className="text-3xl md:text-4xl font-extrabold text-white mt-1.5 tracking-tight">
                  {formatMoney(daily.available)}
                </h2>
              </div>
              <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                <Sparkles className="w-5 h-5" />
              </div>
            </div>
          </div>

          {/* Rollover Badge */}
          <div className="mt-4 pt-3 border-t border-emerald-900/40 flex items-center justify-between">
            <div className="flex items-center gap-1.5 text-xs text-emerald-300">
              <TrendingUp className="w-4 h-4 text-emerald-400" />
              <span className="font-medium">
                {daily.available > dailyTargetCents
                  ? `+${formatMoney(daily.available - dailyTargetCents)} Rollover retained`
                  : 'Compound rollover active'}
              </span>
            </div>
            <span className="text-[11px] text-slate-400">Next top-up at midnight</span>
          </div>
        </div>
      </div>

      {/* Secondary Buckets Row: Vault, Bills, and Freedom Envelope */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        {/* Vault */}
        <div className="p-4 rounded-xl bg-slate-900/80 border border-amber-900/30 flex flex-col justify-between">
          <div>
            <div className="text-[11px] text-amber-300/80 font-medium flex items-center gap-1">
              <Lock className="w-3.5 h-3.5 text-amber-400" />
              <span>Vault Savings</span>
            </div>
            <div className="text-xl font-bold text-white mt-1">{formatMoney(vault.available)}</div>
          </div>
          <div className="mt-2 text-[10px] text-slate-400 flex items-center justify-between">
            <span>{vaultPct}% automatic skim</span>
            <span className="text-amber-400/90 font-medium">Locked</span>
          </div>
        </div>

        {/* Bills */}
        <div className="p-4 rounded-xl bg-slate-900/80 border border-sky-900/30 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <div className="text-[11px] text-sky-300/80 font-medium flex items-center gap-1">
                <Shield className="w-3.5 h-3.5 text-sky-400" />
                <span>Reserved Bills</span>
              </div>
              <button
                type="button"
                onClick={() => {
                  if (onOpenBatchDispatcher) onOpenBatchDispatcher();
                  else setShowBatchModal(true);
                }}
                className="text-[10px] text-sky-300 hover:text-white font-semibold flex items-center gap-1 px-1.5 py-0.5 rounded bg-sky-950/80 border border-sky-800/60 hover:bg-sky-900/70 transition-colors"
                title="Open The Trinity Batch Dispatcher"
              >
                <Zap className="w-3 h-3 text-sky-400" />
                <span>Batch Pay</span>
              </button>
            </div>
            <div className="text-xl font-bold text-white mt-1">{formatMoney(bills.available)}</div>
          </div>
          <div className="mt-2 text-[10px] text-slate-400 flex items-center justify-between">
            <span>Rent &amp; utilities</span>
            <button
              type="button"
              onClick={() => {
                if (onOpenBatchDispatcher) onOpenBatchDispatcher();
                else setShowBatchModal(true);
              }}
              className="text-sky-400/90 hover:text-sky-300 font-medium underline flex items-center gap-0.5"
            >
              <span>Batch Staging</span>
              <ArrowUpRight className="w-2.5 h-2.5" />
            </button>
          </div>
        </div>

        {/* 4. Freedom Envelope */}
        <div className="p-4 rounded-xl bg-gradient-to-br from-purple-950/40 via-slate-900 to-slate-950 border border-purple-800/40 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between text-xs">
              <span className="text-purple-300 font-semibold uppercase tracking-wider">Freedom Envelope</span>
              <span className="text-slate-300 text-xs font-semibold">
                {formatMoney(freedom.available)}
              </span>
            </div>
            <div className="w-full bg-slate-800/80 h-2 rounded-full mt-2.5 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-purple-500 to-indigo-500 transition-all duration-500"
                style={{
                  width: `${Math.min(100, freedomTargetCents > 0 ? (freedom.available / freedomTargetCents) * 100 : 0)}%`
                }}
              />
            </div>
          </div>
          <div className="flex items-center justify-between mt-2.5 text-[11px] text-slate-400">
            <span>of {formatMoney(freedomTargetCents)} limit</span>
            <span className="text-purple-300 font-medium">
              {freedomTargetCents > 0 ? Math.round((freedom.available / freedomTargetCents) * 100) : 0}% left
            </span>
          </div>
        </div>
      </div>

      {/* Analytics & Activity Row: Responsive Grid for Large Screens */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        {/* 5. 7-Day Spending Breakdown with Coach Integration */}
        <div className="p-4 md:p-5 rounded-2xl bg-slate-900/70 border border-slate-800 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">7-Day Spending Activity</span>
              <button
                onClick={() => onAskChart('chart_pie_week')}
                className="text-xs text-emerald-400 hover:text-emerald-300 font-medium flex items-center gap-1 transition-colors"
              >
                <MessageSquareText className="w-3.5 h-3.5" />
                <span>Ask Coach</span>
              </button>
            </div>

            {categoryItems.length > 0 ? (
              <div className="space-y-2.5">
                {categoryItems.map((item) => (
                  <div key={item.category}>
                    <div className="flex justify-between text-xs text-slate-300 mb-1">
                      <span className="capitalize">{item.category.replace('_', ' ')}</span>
                      <span>
                        {item.percentage}% ({formatMoney(item.amount)})
                      </span>
                    </div>
                    <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
                      <div
                        className="h-full bg-emerald-500"
                        style={{ width: `${Math.min(100, item.percentage)}%` }}
                      ></div>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400 py-3">
                No merchant purchases recorded yet. Use Quick Intent or the Coach to evaluate a new purchase.
              </p>
            )}
          </div>
          <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] text-slate-500">
            Updates in real-time as PayPal transactions settle.
          </div>
        </div>

        {/* 6. Coach Dock Quick Actions */}
        <div className="p-4 md:p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 flex flex-col justify-between">
          <div>
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-purple-400 animate-ping"></span>
                <span className="text-xs font-medium text-slate-300">Financial Coach Ready</span>
              </div>
              <button
                onClick={() => onOpenCoach()}
                className="text-xs text-purple-400 hover:text-purple-300 font-semibold flex items-center gap-0.5"
              >
                <span>Open Chat</span>
                <ArrowUpRight className="w-3 h-3" />
              </button>
            </div>

            <p className="text-xs text-slate-400 mt-2">
              Instant guidance on budget limits, double-entry flows, and automated savings sweeps:
            </p>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-3">
              <button
                onClick={() => onOpenCoach('Explain my Bank double-entry flows and where income moved.')}
                className="text-left text-xs p-2.5 bg-slate-800/70 hover:bg-slate-800 border border-slate-700/60 rounded-xl text-slate-300 transition-colors flex items-center gap-1.5"
              >
                <span>🏦 Bank double-entry flows</span>
              </button>
              <button
                onClick={() => onOpenCoach('Explain how my rollover streak works and how unspent Daily funds roll over.')}
                className="text-left text-xs p-2.5 bg-slate-800/70 hover:bg-slate-800 border border-slate-700/60 rounded-xl text-slate-300 transition-colors flex items-center gap-1.5"
              >
                <span>✦ Explain rollover streak</span>
              </button>
              <button
                onClick={() => onOpenCoach('Why is my Bank Foundation bucket locked by default and how does it protect my bills?')}
                className="text-left text-xs p-2.5 bg-slate-800/70 hover:bg-slate-800 border border-slate-700/60 rounded-xl text-slate-300 transition-colors flex items-center gap-1.5"
              >
                <span>🔒 Why is Bank locked?</span>
              </button>
              <button
                onClick={() => onOpenCoach('How does the zero-sum Vault sweep work to automatically build my long-term savings?')}
                className="text-left text-xs p-2.5 bg-slate-800/70 hover:bg-slate-800 border border-slate-700/60 rounded-xl text-slate-300 transition-colors flex items-center gap-1.5"
              >
                <span>⚡ How Vault sweep works</span>
              </button>
              <button
                onClick={() => onOpenCoach('Diagnose my daily burn velocity and financial runway across all Trinity buckets.')}
                className="text-left text-xs p-2.5 bg-slate-800/70 hover:bg-slate-800 border border-slate-700/60 rounded-xl text-slate-300 transition-colors flex items-center gap-1.5"
              >
                <span>📊 Diagnose spend velocity</span>
              </button>
              <button
                onClick={() => onOpenCoach('How does the emergency Escape Window work if I need emergency funds from Bank?')}
                className="text-left text-xs p-2.5 bg-slate-800/70 hover:bg-slate-800 border border-slate-700/60 rounded-xl text-slate-300 transition-colors flex items-center gap-1.5"
              >
                <span>🔥 Escape Window friction</span>
              </button>
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-slate-800/80 text-[11px] text-slate-500">
            Powered by single-call AI reasoning with deterministic guardrails.
          </div>
        </div>
      </div>

      {/* 7. Quick Intent Floating Action Button (FAB) */}
      <div className="fixed bottom-6 right-6 z-30">
        <button
          onClick={onOpenIntent}
          className="flex items-center gap-2 px-5 py-3.5 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-bold rounded-full shadow-xl shadow-emerald-500/20 active:scale-95 transition-all"
        >
          <Zap className="w-5 h-5 fill-current" />
          <span>Quick Intent</span>
        </button>
      </div>

      {/* 8. The Trinity Batch Dispatcher Staging Modal */}
      {showBatchModal && (
        <BatchDispatcherModal
          isOpen={showBatchModal}
          onClose={() => setShowBatchModal(false)}
          onSuccess={() => {
            onSyncSuccess?.();
          }}
        />
      )}
    </div>
  );
}
