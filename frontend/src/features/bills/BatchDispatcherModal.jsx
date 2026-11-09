import React, { useState, useEffect } from 'react';
import {
  X,
  Shield,
  Lock,
  CheckCircle2,
  AlertTriangle,
  Loader2,
  RefreshCw,
  Send,
  Zap,
  Check,
  Ban,
  ArrowRight
} from 'lucide-react';

const formatMoney = (cents) => `$${((cents || 0) / 100).toFixed(2)}`;

export default function BatchDispatcherModal({ isOpen, onClose, onSuccess }) {
  const [loading, setLoading] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [executing, setExecuting] = useState(false);
  const [proposal, setProposal] = useState(null);
  const [queue, setQueue] = useState(null);
  const [approvedItemIds, setApprovedItemIds] = useState(new Set());
  const [sourceBucket, setSourceBucket] = useState('bills');
  const [executionSummary, setExecutionSummary] = useState(null);
  const [error, setError] = useState(null);

  // Load staging proposal & active queue
  const loadStagingData = async (isRefresh = false) => {
    if (isRefresh) setRefreshing(true);
    else setLoading(true);
    setError(null);

    try {
      // 1. Propose batch
      const propRes = await fetch('/api/v1/bills/batch-dispatcher/propose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
      });
      if (!propRes.ok) {
        const errData = await propRes.json().catch(() => ({}));
        throw new Error(errData.detail || 'Failed to generate Batch Dispatcher proposal');
      }
      const propData = await propRes.json();
      setProposal(propData);

      // Default approved items to all recommended items
      const initialApproved = new Set(
        (propData.items || [])
          .filter((it) => it.recommended)
          .map((it) => it.id)
      );
      setApprovedItemIds(initialApproved);

      // 2. Fetch queue
      const qRes = await fetch('/api/v1/bills/batch-dispatcher/queue');
      if (qRes.ok) {
        const qData = await qRes.json();
        setQueue(qData);
      }
    } catch (err) {
      setError(err.message || 'Error loading batch staging area');
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  useEffect(() => {
    if (!isOpen) {
      setProposal(null);
      setQueue(null);
      setExecutionSummary(null);
      setError(null);
      setApprovedItemIds(new Set());
      return;
    }
    loadStagingData();
  }, [isOpen]);

  if (!isOpen) return null;

  // Toggle approval / human veto for an individual item
  const toggleItemVeto = (itemId) => {
    setApprovedItemIds((prev) => {
      const next = new Set(prev);
      if (next.has(itemId)) {
        next.delete(itemId);
      } else {
        next.add(itemId);
      }
      return next;
    });
  };

  // Calculate approved total cents
  const stagedItems = proposal?.items || [];
  const approvedItems = stagedItems.filter((it) => approvedItemIds.has(it.id));
  const totalApprovedCents = approvedItems.reduce((acc, it) => acc + (it.amount_minor || 0), 0);

  // Isolated balances
  const billsAvailCents = queue?.isolated_bills_available_minor ?? proposal?.bills_balance_minor ?? 0;
  const vaultAvailCents = queue?.isolated_vault_available_minor ?? proposal?.vault_balance_minor ?? 0;
  const isolatedReservesCents = billsAvailCents + vaultAvailCents;
  const isOverReserve = totalApprovedCents > (sourceBucket === 'bills' ? isolatedReservesCents : vaultAvailCents);

  // Authorize batch execution
  const handleAuthorizeDispatch = async () => {
    if (approvedItemIds.size === 0) return;
    setExecuting(true);
    setError(null);
    setExecutionSummary(null);

    try {
      const res = await fetch('/api/v1/bills/batch-dispatcher/execute', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          approved_item_ids: Array.from(approvedItemIds),
          source_bucket: sourceBucket,
        }),
      });

      const data = await res.json().catch(() => ({}));

      if (!res.ok) {
        if (res.status === 503) {
          throw new Error(
            data.detail ||
              'Live PayPal Sandbox connection required for batch payout execution. Network offline or credentials unconfigured.'
          );
        }
        throw new Error(data.detail || `Batch execution failed with HTTP ${res.status}`);
      }

      setExecutionSummary(data);

      // Refresh queue after dispatch
      const qRes = await fetch('/api/v1/bills/batch-dispatcher/queue');
      if (qRes.ok) {
        setQueue(await qRes.json());
      }
      onSuccess?.();
    } catch (err) {
      setError(err.message || 'Execution failed');
    } finally {
      setExecuting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md overflow-y-auto animate-fade-in">
      <div className="relative w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden my-8">
        {/* Header */}
        <div className="flex items-center justify-between p-5 border-b border-slate-800 bg-slate-900/90">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-sky-500/10 border border-sky-500/30 flex items-center justify-center text-sky-400">
              <Zap className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-white tracking-tight">The Trinity Batch Dispatcher</h2>
                <span className="px-2 py-0.5 rounded-full bg-sky-950 text-sky-300 border border-sky-800/60 text-[10px] font-semibold uppercase tracking-wider">
                  Staging Area
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Autonomous recurring obligation execution with Human Veto power &amp; Bank Foundation isolation.
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4 max-h-[75vh] overflow-y-auto">
          {/* Blast Radius Containment Banner */}
          <div className="p-4 rounded-xl bg-gradient-to-r from-slate-950 via-slate-900 to-slate-950 border border-slate-800 space-y-3">
            <div className="flex items-center justify-between text-xs">
              <div className="flex items-center gap-2">
                <Shield className="w-4 h-4 text-emerald-400" />
                <span className="font-semibold text-slate-200">Blast Radius Containment</span>
              </div>
              <div className="flex items-center gap-1.5 px-2 py-0.5 rounded-md bg-emerald-950/80 border border-emerald-800/60 text-[11px] font-medium text-emerald-300">
                <Lock className="w-3 h-3 text-emerald-400" />
                <span>Bank Foundation Untouched</span>
              </div>
            </div>

            <div className="grid grid-cols-3 gap-2 pt-1 text-center">
              <div className="p-2.5 rounded-lg bg-slate-900/90 border border-sky-900/40">
                <span className="text-[10px] text-sky-300 uppercase tracking-wider font-semibold block">Reserved Bills</span>
                <span className="text-sm font-bold text-white">{formatMoney(billsAvailCents)}</span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900/90 border border-amber-900/40">
                <span className="text-[10px] text-amber-300 uppercase tracking-wider font-semibold block">Vault Savings</span>
                <span className="text-sm font-bold text-white">{formatMoney(vaultAvailCents)}</span>
              </div>
              <div className="p-2.5 rounded-lg bg-slate-900/90 border border-emerald-900/40">
                <span className="text-[10px] text-emerald-300 uppercase tracking-wider font-semibold block">Bank Foundation</span>
                <span className="text-sm font-bold text-emerald-400">Protected</span>
              </div>
            </div>

            {/* Source Bucket Selector */}
            <div className="flex items-center justify-between pt-2 text-xs border-t border-slate-800/80">
              <span className="text-slate-400">Execution Reserve Source:</span>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={() => setSourceBucket('bills')}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
                    sourceBucket === 'bills'
                      ? 'bg-sky-950 border-sky-600 text-sky-200'
                      : 'bg-slate-800/50 border-slate-700 text-slate-400 hover:text-white'
                  }`}
                >
                  Reserved Bills
                </button>
                <button
                  type="button"
                  onClick={() => setSourceBucket('vault')}
                  className={`px-2.5 py-1 rounded-lg text-xs font-medium border transition-colors ${
                    sourceBucket === 'vault'
                      ? 'bg-amber-950 border-amber-600 text-amber-200'
                      : 'bg-slate-800/50 border-slate-700 text-slate-400 hover:text-white'
                  }`}
                >
                  Vault Reserve
                </button>
              </div>
            </div>
          </div>

          {/* AI Coach Proposal Card */}
          {proposal && (
            <div className="p-4 rounded-xl bg-purple-950/20 border border-purple-800/40 space-y-2.5">
              <div className="flex items-center justify-between">
                <span className="text-xs font-semibold text-purple-300 uppercase tracking-wider">AI Coach Staging Proposal</span>
                <button
                  onClick={() => loadStagingData(true)}
                  disabled={refreshing || executing}
                  className="flex items-center gap-1 text-[11px] text-purple-300 hover:text-purple-200 transition-colors disabled:opacity-50"
                  title="Re-analyze obligations"
                >
                  <RefreshCw className={`w-3 h-3 ${refreshing ? 'animate-spin' : ''}`} />
                  <span>Refresh Staging</span>
                </button>
              </div>
              <p className="text-xs text-slate-300 leading-relaxed">{proposal.coach_message}</p>
              {proposal.risk_assessment && (
                <div className="p-2 rounded-lg bg-slate-900/90 border border-purple-900/40 text-[11px] text-slate-400 flex items-start gap-1.5">
                  <Shield className="w-3.5 h-3.5 text-purple-400 shrink-0 mt-0.5" />
                  <span>{typeof proposal.risk_assessment === 'string' ? proposal.risk_assessment : JSON.stringify(proposal.risk_assessment)}</span>
                </div>
              )}
            </div>
          )}

          {/* Error / Alert Banner */}
          {error && (
            <div className="p-3.5 rounded-xl bg-rose-950/40 border border-rose-800/60 flex items-start gap-2.5 text-xs text-rose-300">
              <AlertTriangle className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-rose-200">Execution Blocked</p>
                <p className="mt-0.5 leading-relaxed">{error}</p>
              </div>
            </div>
          )}

          {/* Over Reserve Warning */}
          {isOverReserve && (
            <div className="p-3.5 rounded-xl bg-amber-950/40 border border-amber-800/60 flex items-start gap-2.5 text-xs text-amber-300">
              <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0 mt-0.5" />
              <div>
                <p className="font-semibold text-amber-200">Reserve Protection Active</p>
                <p className="mt-0.5">
                  Total approved ({formatMoney(totalApprovedCents)}) exceeds available isolated reserve (
                  {formatMoney(sourceBucket === 'bills' ? isolatedReservesCents : vaultAvailCents)}). Bank Foundation cannot be
                  raided. Veto some items to proceed.
                </p>
              </div>
            </div>
          )}

          {/* Interactive Staged Items Checklist */}
          <div className="space-y-2">
            <div className="flex items-center justify-between text-xs text-slate-400 px-1">
              <span className="font-semibold uppercase tracking-wider text-slate-300">Staged Obligations (Human Veto Gate)</span>
              <span>{approvedItemIds.size} of {stagedItems.length} approved</span>
            </div>

            {loading ? (
              <div className="py-8 flex flex-col items-center justify-center gap-2 text-slate-400">
                <Loader2 className="w-6 h-6 animate-spin text-sky-400" />
                <span className="text-xs">Analyzing scheduled bills &amp; isolated reserves...</span>
              </div>
            ) : stagedItems.length === 0 ? (
              <div className="py-8 text-center text-xs text-slate-400 border border-dashed border-slate-800 rounded-xl">
                No pending obligations found to stage. Add bills or stage payments from Quick Intent or Coach to queue them for batch dispatch.
              </div>
            ) : (
              <div className="space-y-2">
                {stagedItems.map((item) => {
                  const isApproved = approvedItemIds.has(item.id);
                  return (
                    <div
                      key={item.id}
                      className={`p-3 rounded-xl border transition-all flex items-center justify-between gap-3 ${
                        isApproved
                          ? 'bg-slate-900/90 border-slate-700 hover:border-slate-600'
                          : 'bg-slate-950/60 border-slate-800/60 opacity-60'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <button
                          type="button"
                          disabled={executing}
                          onClick={() => toggleItemVeto(item.id)}
                          className={`w-6 h-6 rounded-md border flex items-center justify-center transition-colors ${
                            isApproved
                              ? 'bg-emerald-600 border-emerald-500 text-white'
                              : 'bg-slate-800 border-slate-700 text-transparent hover:border-slate-600'
                          }`}
                          title={isApproved ? 'Click to veto this item' : 'Click to approve this item'}
                        >
                          <Check className="w-3.5 h-3.5" />
                        </button>
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="text-sm font-semibold text-white">{item.title}</span>
                            <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-slate-800 text-slate-300 border border-slate-700">
                              {item.category || 'Bills'}
                            </span>
                            {item.intent_id ? (
                              <span className="px-1.5 py-0.2 rounded text-[9px] font-semibold bg-emerald-950 text-emerald-300 border border-emerald-800/60">
                                Quick Intent
                              </span>
                            ) : !item.bill_id ? (
                              <span className="px-1.5 py-0.2 rounded text-[9px] font-semibold bg-indigo-950 text-indigo-300 border border-indigo-800/60">
                                Coach Memory
                              </span>
                            ) : null}
                            {item.recommended && (
                              <span className="px-1.5 py-0.2 rounded text-[9px] font-semibold bg-purple-950 text-purple-300 border border-purple-800/60">
                                Recommended
                              </span>
                            )}
                          </div>
                          <p className="text-[11px] text-slate-400 mt-0.5">
                            Payee: <span className="text-slate-300">{item.recipient_email || item.payee_email || 'Unspecified'}</span>
                            {item.due_date && <span> &bull; Due: {item.due_date}</span>}
                          </p>
                        </div>
                      </div>

                      <div className="text-right shrink-0">
                        <span className="text-sm font-bold text-white block">{formatMoney(item.amount_minor)}</span>
                        <span
                          className={`text-[10px] font-medium uppercase tracking-wider ${
                            isApproved ? 'text-emerald-400' : 'text-slate-500'
                          }`}
                        >
                          {isApproved ? 'Approved' : 'Vetoed'}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Sequential Execution Summary */}
          {executionSummary && (
            <div className="p-4 rounded-xl bg-emerald-950/30 border border-emerald-800/60 space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <CheckCircle2 className="w-4 h-4 text-emerald-400" />
                  <span className="text-xs font-semibold text-emerald-300 uppercase tracking-wider">
                    Sequential Dispatch Completed
                  </span>
                </div>
                <span className="text-xs font-bold text-white">
                  {executionSummary.executed_count} executed ({formatMoney(executionSummary.total_amount_minor)})
                </span>
              </div>
              <p className="text-xs text-slate-300">{executionSummary.message}</p>

              {executionSummary.results && executionSummary.results.length > 0 && (
                <div className="space-y-1.5 pt-1">
                  {executionSummary.results.map((res) => (
                    <div
                      key={res.item_id}
                      className="p-2 rounded-lg bg-slate-900/90 border border-slate-800 flex items-center justify-between text-xs"
                    >
                      <span className="text-slate-200 font-medium">{res.title}</span>
                      <div className="flex items-center gap-2">
                        {res.status === 'paid' ? (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-emerald-950 text-emerald-300 border border-emerald-800">
                            Paid ({res.paypal_payout_id || 'SUCCESS'})
                          </span>
                        ) : (
                          <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-rose-950 text-rose-300 border border-rose-800">
                            Failed: {res.error_message || 'Denied'}
                          </span>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Footer Actions */}
        <div className="flex items-center justify-between p-5 border-t border-slate-800 bg-slate-900/90">
          <div>
            <span className="text-[11px] text-slate-400 uppercase tracking-wider block">Total Approved</span>
            <span className="text-base font-extrabold text-white">
              {formatMoney(totalApprovedCents)}{' '}
              <span className="text-xs font-normal text-slate-400">({approvedItemIds.size} items)</span>
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={executing}
              className="px-4 py-2 rounded-xl text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            >
              Close
            </button>
            <button
              type="button"
              onClick={handleAuthorizeDispatch}
              disabled={executing || approvedItemIds.size === 0 || isOverReserve || loading}
              className="flex items-center gap-1.5 px-4 py-2 rounded-xl text-xs font-bold text-white bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:hover:bg-emerald-600 transition-colors shadow-lg shadow-emerald-950/50"
            >
              {executing ? (
                <>
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  <span>Dispatching...</span>
                </>
              ) : (
                <>
                  <Send className="w-3.5 h-3.5" />
                  <span>Authorize Batch Dispatch</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
