import React from 'react';
import { Shield, Lock, Sparkles, TrendingUp, AlertCircle, ArrowUpRight, MessageSquareText, Zap } from 'lucide-react';

export default function MobileHUD({
  buckets,
  stats,
  onOpenIntent,
  onOpenCoach,
  onAskChart,
  onTriggerOverride
}) {
  const bank = buckets?.find(b => b.kind === 'bank') || { available: 80000 };
  const daily = buckets?.find(b => b.kind === 'daily') || { available: 5200 };
  const freedom = buckets?.find(b => b.kind === 'freedom') || { available: 9000 };
  const vault = buckets?.find(b => b.kind === 'vault') || { available: 20000 };
  const bills = buckets?.find(b => b.kind === 'bills') || { available: 120000 };

  const formatMoney = (cents) => `$${(cents / 100).toFixed(2)}`;

  return (
    <div className="max-w-md mx-auto px-4 py-6 space-y-4 pb-28">
      {/* Top Header */}
      <div className="flex items-center justify-between pb-2 border-b border-slate-800">
        <div>
          <div className="flex items-center gap-2">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-500 animate-pulse"></span>
            <h1 className="text-xl font-bold tracking-tight text-white">FireWallet</h1>
          </div>
          <p className="text-xs text-slate-400">Trinity Financial Firewall & Coach</p>
        </div>
        <div className="flex items-center gap-1.5 px-2.5 py-1 bg-slate-900 border border-slate-800 rounded-full text-xs text-slate-300">
          <Shield className="w-3.5 h-3.5 text-emerald-400" />
          <span>Firewall Active</span>
        </div>
      </div>

      {/* 1. Bank Foundation Card */}
      <div className="p-4 rounded-2xl bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800 shadow-sm relative overflow-hidden">
        <div className="flex items-start justify-between">
          <div>
            <span className="text-xs uppercase tracking-wider font-semibold text-slate-400">Foundation</span>
            <h2 className="text-2xl font-bold text-white mt-0.5">{formatMoney(bank.available)}</h2>
            <div className="flex items-center gap-1 text-xs text-slate-400 mt-1">
              <Lock className="w-3.5 h-3.5 text-amber-400" />
              <span>Direct spend locked &middot; Safeguards cash flow</span>
            </div>
          </div>
          <span className="px-2.5 py-1 rounded-full bg-slate-800/80 border border-slate-700 text-[11px] font-medium text-slate-300">
            Bank Bucket
          </span>
        </div>
      </div>

      {/* 2. Daily Allowance Hero Card (with Rollover) */}
      <div className="p-5 rounded-2xl bg-gradient-to-br from-emerald-950/70 via-slate-900 to-slate-950 border border-emerald-800/60 shadow-lg relative">
        <div className="flex items-start justify-between">
          <div>
            <div className="flex items-center gap-1.5">
              <span className="text-xs uppercase tracking-wider font-semibold text-emerald-400">Daily Living Engine</span>
              <span className="px-2 py-0.5 rounded-full bg-emerald-500/20 text-emerald-300 text-[10px] font-medium">
                Target: $40.00
              </span>
            </div>
            <h2 className="text-4xl font-extrabold text-white mt-1.5 tracking-tight">
              {formatMoney(daily.available)}
            </h2>
          </div>
          <div className="w-10 h-10 rounded-xl bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
            <Sparkles className="w-5 h-5" />
          </div>
        </div>

        {/* Rollover Badge */}
        <div className="mt-3.5 pt-3 border-t border-emerald-900/40 flex items-center justify-between">
          <div className="flex items-center gap-1.5 text-xs text-emerald-300">
            <TrendingUp className="w-4 h-4 text-emerald-400" />
            <span className="font-medium">+$12.00 Rollover retained</span>
          </div>
          <span className="text-[11px] text-slate-400">Next top-up at midnight</span>
        </div>
      </div>

      {/* 3. Out-of-Sight Safe Reserves Strip (Vault & Bills) */}
      <div className="grid grid-cols-2 gap-3">
        {/* Vault */}
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-amber-900/30 flex items-center justify-between">
          <div>
            <div className="text-[11px] text-amber-300/80 font-medium flex items-center gap-1">
              <Lock className="w-3 h-3 text-amber-400" />
              <span>Vault Savings</span>
            </div>
            <div className="text-lg font-bold text-white mt-0.5">{formatMoney(vault.available)}</div>
            <span className="text-[10px] text-slate-400">20% auto-skimmed</span>
          </div>
        </div>

        {/* Bills */}
        <div className="p-3.5 rounded-xl bg-slate-900/80 border border-sky-900/30 flex items-center justify-between">
          <div>
            <div className="text-[11px] text-sky-300/80 font-medium flex items-center gap-1">
              <Shield className="w-3 h-3 text-sky-400" />
              <span>Reserved Bills</span>
            </div>
            <div className="text-lg font-bold text-white mt-0.5">{formatMoney(bills.available)}</div>
            <span className="text-[10px] text-slate-400">Rent & utilities first</span>
          </div>
        </div>
      </div>

      {/* 4. Freedom Envelope (Discretionary / Hedonism) */}
      <div className="p-4 rounded-2xl bg-gradient-to-br from-purple-950/40 via-slate-900 to-slate-950 border border-purple-800/40">
        <div className="flex items-center justify-between text-xs">
          <span className="text-purple-300 font-semibold uppercase tracking-wider">Freedom Envelope</span>
          <span className="text-slate-300">{formatMoney(freedom.available)} / $150.00 left</span>
        </div>
        <div className="w-full bg-slate-800/80 h-2 rounded-full mt-2.5 overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-purple-500 to-indigo-500 transition-all duration-500"
            style={{ width: `${Math.min(100, (freedom.available / 15000) * 100)}%` }}
          />
        </div>
        <div className="flex items-center justify-between mt-2 text-[11px] text-slate-400">
          <span>Guilt-free fun money</span>
          <span>{Math.round((freedom.available / 15000) * 100)}% remaining</span>
        </div>
      </div>

      {/* 5. 7-Day Spending Breakdown with Coach Integration */}
      <div className="p-4 rounded-2xl bg-slate-900/70 border border-slate-800">
        <div className="flex items-center justify-between mb-3">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-300">7-Day Spending Analytics</span>
          <button
            onClick={() => onAskChart('chart_pie_week')}
            className="text-xs text-emerald-400 hover:text-emerald-300 font-medium flex items-center gap-1 transition-colors"
          >
            <MessageSquareText className="w-3.5 h-3.5" />
            <span>Ask Coach</span>
          </button>
        </div>

        {/* Lightweight SVG Category Bar */}
        <div className="space-y-2">
          <div>
            <div className="flex justify-between text-xs text-slate-300 mb-1">
              <span>Groceries (Daily)</span>
              <span>66.7% ($80.00)</span>
            </div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
              <div className="h-full bg-emerald-500" style={{ width: '66.7%' }}></div>
            </div>
          </div>
          <div>
            <div className="flex justify-between text-xs text-slate-300 mb-1">
              <span>Dining Out (Freedom)</span>
              <span>33.3% ($40.00)</span>
            </div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
              <div className="h-full bg-purple-500" style={{ width: '33.3%' }}></div>
            </div>
          </div>
        </div>
      </div>

      {/* 6. Coach Dock Quick Actions */}
      <div className="p-4 rounded-2xl bg-slate-900/60 border border-slate-800/80">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="w-2 h-2 rounded-full bg-purple-400 animate-ping"></span>
            <span className="text-xs font-medium text-slate-300">Financial Coach Active</span>
          </div>
          <button
            onClick={() => onOpenCoach()}
            className="text-xs text-purple-400 hover:text-purple-300 font-medium flex items-center gap-0.5"
          >
            <span>Open Chat</span>
            <ArrowUpRight className="w-3 h-3" />
          </button>
        </div>

        <div className="flex gap-2 mt-2.5 overflow-x-auto pb-1 scrollbar-none">
          <button
            onClick={() => onOpenCoach('Explain how my rollover streak works and how unspent Daily funds roll over.')}
            className="text-xs px-3 py-1.5 bg-slate-800/70 hover:bg-slate-800 border border-slate-700/60 rounded-full text-slate-300 whitespace-nowrap transition-colors flex items-center gap-1 shrink-0"
          >
            <span>✦ Explain rollover streak</span>
          </button>
          <button
            onClick={() => onOpenCoach('Why is my Bank Foundation bucket locked by default and how does it protect my bills?')}
            className="text-xs px-3 py-1.5 bg-slate-800/70 hover:bg-slate-800 border border-slate-700/60 rounded-full text-slate-300 whitespace-nowrap transition-colors flex items-center gap-1 shrink-0"
          >
            <span>🔒 Why is Bank locked?</span>
          </button>
          <button
            onClick={() => onOpenCoach('How does the zero-sum Vault sweep work to automatically build my long-term savings?')}
            className="text-xs px-3 py-1.5 bg-slate-800/70 hover:bg-slate-800 border border-slate-700/60 rounded-full text-slate-300 whitespace-nowrap transition-colors flex items-center gap-1 shrink-0"
          >
            <span>⚡ How Vault sweep works</span>
          </button>
          <button
            onClick={() => onOpenCoach('Diagnose my daily burn velocity and financial runway across all Trinity buckets.')}
            className="text-xs px-3 py-1.5 bg-slate-800/70 hover:bg-slate-800 border border-slate-700/60 rounded-full text-slate-300 whitespace-nowrap transition-colors flex items-center gap-1 shrink-0"
          >
            <span>📊 Diagnose spend velocity</span>
          </button>
          <button
            onClick={() => onOpenCoach('How does the emergency Escape Window work if I need emergency funds from Bank?')}
            className="text-xs px-3 py-1.5 bg-slate-800/70 hover:bg-slate-800 border border-slate-700/60 rounded-full text-slate-300 whitespace-nowrap transition-colors flex items-center gap-1 shrink-0"
          >
            <span>🔥 Escape Window friction</span>
          </button>
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
    </div>
  );
}
