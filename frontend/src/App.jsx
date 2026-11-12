import React, { useState, useEffect, useCallback } from 'react';
import { Smartphone, LayoutGrid, Sparkles } from 'lucide-react';
import MobileHUD from './features/hud/MobileHUD';
import BucketConfigModal from './features/hud/BucketConfigModal';
import QuickIntentModal from './features/intent/QuickIntentModal';
import EscapeWindowModal from './features/override/EscapeWindowModal';
import BatchDispatcherModal from './features/bills/BatchDispatcherModal';
import { CoachDrawer } from './features/coach/CoachDrawer';
import DeepLedgerGrid from './features/analytics/DeepLedgerGrid';
import { fetchBuckets, fetchStatsSummary, captureIntent } from './shared/api';
import { useToast } from './features/notifications/ToastContext';

export default function App() {
  const { showToast } = useToast();
  const [view, setView] = useState(() => {
    if (typeof window !== 'undefined') {
      if (
        window.location.pathname.includes('/analytics') ||
        new URLSearchParams(window.location.search).get('view') === 'deep-ledger'
      ) {
        return 'deep-ledger';
      }
    }
    return 'hud';
  });
  const [buckets, setBuckets] = useState([
    { kind: 'bank', name: 'Bank Foundation', available: 0 },
    { kind: 'daily', name: 'Daily', available: 0 },
    { kind: 'freedom', name: 'Freedom', available: 0 },
    { kind: 'vault', name: 'Vault', available: 0 },
    { kind: 'bills', name: 'Reserved Bills', available: 0 }
  ]);
  const [stats, setStats] = useState(null);
  const [ledgerRefreshTick, setLedgerRefreshTick] = useState(0);

  // Modals state
  const [isIntentOpen, setIsIntentOpen] = useState(() => {
    return typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('modal') === 'intent';
  });
  const [isConfigOpen, setIsConfigOpen] = useState(false);
  const [isOverrideOpen, setIsOverrideOpen] = useState(false);
  const [isBatchDispatcherOpen, setIsBatchDispatcherOpen] = useState(() => {
    return typeof window !== 'undefined' && new URLSearchParams(window.location.search).get('modal') === 'batch';
  });
  const [activeOverrideIntentId, setActiveOverrideIntentId] = useState(null);

  // Coach Drawer state
  const [isCoachOpen, setIsCoachOpen] = useState(false);
  const [coachInitialQuery, setCoachInitialQuery] = useState('');
  const [coachChartContext, setCoachChartContext] = useState(null);
  const [coachFilterContext, setCoachFilterContext] = useState(null);

  const loadData = useCallback(async () => {
    try {
      const bRes = await fetchBuckets();
      if (bRes.buckets) setBuckets(bRes.buckets);
      const sRes = await fetchStatsSummary();
      setStats(sRes);
      setLedgerRefreshTick(t => t + 1);
    } catch (err) {
      console.warn('API running offline or starting up, using cached state.');
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // PayPal Redirect Return & Cancel Listener
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const isReturn = params.get('paypal_return') === 'true';
    const isCancel = params.get('paypal_cancel') === 'true';
    const token = params.get('token');
    const payerId = params.get('PayerID') || params.get('payer_id');
    const intentId = params.get('intent_id');

    if (isReturn && token && intentId) {
      showToast({
        type: 'processing',
        title: 'Verifying PayPal Checkout',
        message: 'Verifying and capturing PayPal sandbox payment...',
        details: `Order: ${token}`,
        duration: 4000,
      });

      // Clear search params from URL so refresh does not re-trigger
      window.history.replaceState({}, document.title, window.location.pathname);

      captureIntent(intentId, token, payerId)
        .then((res) => {
          showToast({
            type: 'order_success',
            title: 'PayPal Payment Settled',
            message: 'PayPal payment approved & captured successfully! Double-entry ledger updated.',
            details: `Order: ${res.paypal_order_id || token} · Capture: ${res.paypal_capture_id}`,
            duration: 5000,
          });
          loadData();
        })
        .catch((err) => {
          const isUnapproved = err.message?.includes('ORDER_NOT_APPROVED');
          showToast({
            type: 'error',
            title: isUnapproved ? 'Order Not Approved' : 'PayPal Capture Failed',
            message: isUnapproved
              ? 'PayPal Order not approved yet. Buyer approval was not completed.'
              : `PayPal capture failed: ${err.message || 'Unknown error'}`,
            details: `Order: ${token}`,
            duration: 6000,
          });
        });
    } else if (isCancel) {
      showToast({
        type: 'cancel',
        title: 'PayPal Checkout Cancelled',
        message: 'PayPal checkout was cancelled. No funds were debited.',
        details: token ? `Order: ${token}` : null,
        duration: 4500,
      });
      window.history.replaceState({}, document.title, window.location.pathname);
    }
  }, [loadData, showToast]);

  const handleOpenCoachWithQuery = useCallback((query, chartId = null, filterContext = null) => {
    if (!query) {
      setIsCoachOpen(true);
      return;
    }
    setCoachInitialQuery({
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      text: query,
      chartId,
      filterContext
    });
    setCoachChartContext(chartId);
    setCoachFilterContext(filterContext);
    setIsCoachOpen(true);
  }, []);

  const handleClearInitialQuery = useCallback(() => {
    setCoachInitialQuery(null);
  }, []);

  const handleOpenOverride = useCallback((intentId) => {
    setActiveOverrideIntentId(intentId);
    setIsOverrideOpen(true);
  }, []);

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
            onOpenConfig={() => setIsConfigOpen(true)}
            onOpenBatchDispatcher={() => setIsBatchDispatcherOpen(true)}
            onSyncSuccess={loadData}
          />
        ) : (
          <div className="flex flex-col lg:flex-row flex-1 min-h-[calc(100vh-61px)]">
            <div className="flex-1 min-w-0">
              <DeepLedgerGrid
                refreshTrigger={ledgerRefreshTick}
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
                onClearInitialQuery={handleClearInitialQuery}
                chartContext={coachChartContext}
                filterContext={coachFilterContext}
                mode="sidebar"
                onOpenOverride={handleOpenOverride}
                onActionSuccess={loadData}
                onSelectSuggestIntent={() => {
                  setIsIntentOpen(true);
                }}
              />
            )}
          </div>
        )}
      </main>

      {/* Modals */}
      <BucketConfigModal
        isOpen={isConfigOpen}
        onClose={() => setIsConfigOpen(false)}
        onSuccess={loadData}
      />

      <QuickIntentModal
        isOpen={isIntentOpen}
        onClose={() => setIsIntentOpen(false)}
        onOpenOverride={handleOpenOverride}
        onAskCoach={(q) => handleOpenCoachWithQuery(q)}
        onOpenBatchDispatcher={() => {
          setIsIntentOpen(false);
          setIsBatchDispatcherOpen(true);
        }}
        onSuccess={loadData}
      />

      <EscapeWindowModal
        isOpen={isOverrideOpen}
        onClose={() => setIsOverrideOpen(false)}
        intentId={activeOverrideIntentId}
        onSuccess={loadData}
      />

      <BatchDispatcherModal
        isOpen={isBatchDispatcherOpen}
        onClose={() => setIsBatchDispatcherOpen(false)}
        onSuccess={loadData}
      />

      {/* Mobile Drawer (Only active when in 'hud' view mode) */}
      {view === 'hud' && isCoachOpen && (
        <CoachDrawer
          isOpen={isCoachOpen}
          onClose={() => setIsCoachOpen(false)}
          initialQuery={coachInitialQuery}
          onClearInitialQuery={handleClearInitialQuery}
          chartContext={coachChartContext}
          filterContext={coachFilterContext}
          mode="drawer"
          onOpenOverride={handleOpenOverride}
          onActionSuccess={loadData}
          onSelectSuggestIntent={() => {
            setIsIntentOpen(true);
          }}
        />
      )}
    </div>
  );
}
