import React, { useState, useEffect } from 'react';
import { Smartphone, LayoutGrid, Sparkles } from 'lucide-react';
import MobileHUD from './features/hud/MobileHUD';
import QuickIntentModal from './features/intent/QuickIntentModal';
import EscapeWindowModal from './features/override/EscapeWindowModal';
import {CoachDrawer} from './features/coach/CoachDrawer';
import DeepLedgerGrid from './features/analytics/DeepLedgerGrid';
import { fetchBuckets, fetchStatsSummary } from './shared/api';

export default function App() {
  const [view, setView] = useState('hud'); // 'hud' or 'deep-ledger'
  const [buckets, setBuckets] = useState([
    { kind: 'bank', name: 'Bank', available: 80000 },
    { kind: 'daily', name: 'Daily Allowance', available: 5200 },
    { kind: 'freedom', name: 'Freedom', available: 9000 },
    { kind: 'vault', name: 'Vault', available: 20000 },
    { kind: 'bills', name: 'Bills', available: 120000 }
  ]);
  const [stats, setStats] = useState(null);

  // Modals state
  const [isIntentOpen, setIsIntentOpen] = useState(false);
  const [isOverrideOpen, setIsOverrideOpen] = useState(false);
  const [activeOverrideIntentId, setActiveOverrideIntentId] = useState(null);

  // Coach Drawer state
  const [isCoachOpen, setIsCoachOpen] = useState(false);
  const [coachInitialQuery, setCoachInitialQuery] = useState('');
  const [coachChartContext, setCoachChartContext] = useState(null);
  const [coachFilterContext, setCoachFilterContext] = useState(null);

  const loadData = async () => {
    try {
      const bRes = await fetchBuckets();
      if (bRes.buckets) setBuckets(bRes.buckets);
      const sRes = await fetchStatsSummary();
      setStats(sRes);
    } catch (err) {
      console.warn('API running offline or starting up, using cached state.');
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleOpenCoachWithQuery = (query, chartId = null, filterContext = null) => {
    setCoachInitialQuery(query);
    setCoachChartContext(chartId);
    setCoachFilterContext(filterContext);
    setIsCoachOpen(true);
  };

  const handleOpenOverride = (intentId) => {
    setActiveOverrideIntentId(intentId);
    setIsOverrideOpen(true);
  };

  return (
    <div className="min-h-screen bg-[#090d16] text-slate-100 flex flex-col font-sans">
      {/* Top Navigation Bar with View Toggle */}
      <header className="sticky top-0 z-40 bg-slate-950/80 backdrop-blur-md border-b border-slate-800/80 px-4 py-3">
        <div className="max-w-[1440px] mx-auto flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <span className="w-2.5 h-2.5 rounded-full bg-emerald-400"></span>
            <span className="font-extrabold tracking-tight text-white text-base">FireWallet</span>
            <span className="hidden sm:inline-block text-[11px] px-2 py-0.5 rounded-full bg-slate-800 text-slate-400 border border-slate-700">
              Trinity Engine
            </span>
          </div>

          {/* Right Header Navigation & Actions */}
          <div className="flex items-center gap-2">
            {/* View Mode Switcher */}
            <div className="flex items-center bg-slate-900 border border-slate-800 rounded-xl p-1 text-xs">
              <button
                onClick={() => setView('hud')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
                  view === 'hud'
                    ? 'bg-emerald-500 text-slate-950 font-bold shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <Smartphone className="w-3.5 h-3.5" />
                <span>Mobile HUD</span>
              </button>

              <button
                onClick={() => setView('deep-ledger')}
                className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg font-medium transition-all ${
                  view === 'deep-ledger'
                    ? 'bg-purple-600 text-white font-bold shadow-sm'
                    : 'text-slate-400 hover:text-white'
                }`}
              >
                <LayoutGrid className="w-3.5 h-3.5" />
                <span>Deep Analytics</span>
              </button>
            </div>

            {/* Desktop Coach Sidebar Toggle Button */}
            {view === 'deep-ledger' && (
              <button
                onClick={() => setIsCoachOpen(prev => !prev)}
                className={`hidden md:flex items-center gap-1.5 px-3 py-2 text-xs font-semibold rounded-xl border transition-all ${
                  isCoachOpen
                    ? 'bg-purple-600 text-white border-purple-500 shadow-md'
                    : 'bg-slate-900 hover:bg-slate-800 text-slate-300 border-slate-800'
                }`}
                title="Toggle AI Coach Sidebar"
              >
                <Sparkles className="w-3.5 h-3.5 text-purple-400" />
                <span>{isCoachOpen ? 'Close Coach' : 'Open Coach'}</span>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main View Area */}
      <main className="flex-1">
        {view === 'hud' ? (
          <MobileHUD
            buckets={buckets}
            stats={stats}
            onOpenIntent={() => setIsIntentOpen(true)}
            onOpenCoach={(q) => handleOpenCoachWithQuery(q || '')}
            onAskChart={(chartId) => handleOpenCoachWithQuery('What does this 7-day spending chart mean?', chartId)}
            onTriggerOverride={handleOpenOverride}
          />
        ) : (
          <div className="flex flex-col lg:flex-row flex-1 min-h-[calc(100vh-61px)]">
            <div className="flex-1 min-w-0">
              <DeepLedgerGrid
                onAnalyzeWithCoach={(query, filterCtx) => {
                  handleOpenCoachWithQuery(query, null, filterCtx);
                }}
                isCoachOpen={isCoachOpen}
                onToggleCoach={() => setIsCoachOpen(prev => !prev)}
              />
            </div>

            {/* Side-by-side Coach Sidebar for Desktop AG Grid workbench */}
            {isCoachOpen && (
              <CoachDrawer
                isOpen={isCoachOpen}
                onClose={() => setIsCoachOpen(false)}
                initialQuery={coachInitialQuery}
                chartContext={coachChartContext}
                filterContext={coachFilterContext}
                mode="sidebar"
                onSelectSuggestIntent={(suggestion) => {
                  setIsIntentOpen(true);
                }}
              />
            )}
          </div>
        )}
      </main>

      {/* Modals */}
      <QuickIntentModal
        isOpen={isIntentOpen}
        onClose={() => setIsIntentOpen(false)}
        onOpenOverride={handleOpenOverride}
        onSuccess={loadData}
      />

      <EscapeWindowModal
        isOpen={isOverrideOpen}
        onClose={() => setIsOverrideOpen(false)}
        intentId={activeOverrideIntentId}
        onSuccess={loadData}
      />

      {/* Mobile Drawer (Only active when in 'hud' view mode) */}
      {view === 'hud' && isCoachOpen && (
        <CoachDrawer
          isOpen={isCoachOpen}
          onClose={() => setIsCoachOpen(false)}
          initialQuery={coachInitialQuery}
          chartContext={coachChartContext}
          filterContext={coachFilterContext}
          mode="drawer"
          onSelectSuggestIntent={(suggestion) => {
            setIsIntentOpen(true);
          }}
        />
      )}
    </div>
  );
}
