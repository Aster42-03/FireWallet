/**
 * CoachDrawer - Unified Monolithic AI Financial Coach Interface
 * =============================================================
 * Dual-mode conversational panel powered by Single-Call AI Engine (`CoachDecision`)
 * + deterministic `LedgerEngine` guardrails + RAG `short_tag` memory:
 * 1. 'sidebar': Desktop side-by-side pane alongside AG Grid workbench.
 * 2. 'drawer': Mobile slide-over modal accessible from the HUD.
 *
 * Includes:
 * - StrictMode-safe deduplication (`lastProcessedInitialRef`, `isSendingRef`, `AbortController`) fixing BUG-001.
 * - Pre-filled 1-Tap `ActionCard` buttons (PayPal Sandbox Checkout, Zero-Sum Vault Sweep, Escape Window).
 * - Recorded `short_tag` pills & RAG historical memory citation chips.
 */

import React, { useState, useRef, useEffect, useCallback } from 'react';
import {
  X,
  Send,
  Sparkles,
  Loader2,
  ShieldCheck,
  Activity,
  BarChart2,
  Tag,
  CheckCircle2,
  ExternalLink,
  Vault,
  Lock,
  Zap,
  Database
} from 'lucide-react';
import { sendCoachMessage, executeCoachAction, fetchCoachStatus, captureIntent } from '../../shared/api';
import { MarkdownRenderer } from './MarkdownRenderer';

export function CoachDrawer({
  isOpen,
  onClose,
  initialQuery = '',
  onClearInitialQuery,
  chartContext = null,
  filterContext = null,
  onSelectSuggestIntent,
  onOpenOverride,
  onActionSuccess,
  mode = 'drawer' // 'drawer' (modal overlay) or 'sidebar' (side-by-side pane)
}) {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content:
        'Hello! I am your Financial Coach. Ask me if a purchase fits your budget, sweep funds into your Vault, handle an urgent emergency, or inspect your double-entry ledger — and I will prepare a 1-tap action card for you.',
      displayedContent:
        'Hello! I am your Financial Coach. Ask me if a purchase fits your budget, sweep funds into your Vault, handle an urgent emergency, or inspect your double-entry ledger — and I will prepare a 1-tap action card for you.',
      isStreaming: false
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [threadId, setThreadId] = useState(null);
  const [executingMsgId, setExecutingMsgId] = useState(null);
  const [executedResults, setExecutedResults] = useState({});
  const [coachStatus, setCoachStatus] = useState(null);

  // Synchronous deduplication and abort refs
  const isSendingRef = useRef(false);
  const lastProcessedIdRef = useRef('');
  const abortControllerRef = useRef(null);
  const inputRef = useRef('');
  inputRef.current = input;

  // Auto-scroll and streaming refs
  const messagesEndRef = useRef(null);
  const messagesContainerRef = useRef(null);
  const streamIntervalRef = useRef(null);

  const scrollToBottom = useCallback((behavior = 'smooth') => {
    if (messagesEndRef.current) {
      messagesEndRef.current.scrollIntoView({ behavior, block: 'end' });
    }
  }, []);

  // Fetch live AI engine connectivity status
  useEffect(() => {
    let isMounted = true;
    fetchCoachStatus()
      .then(st => {
        if (isMounted) setCoachStatus(st);
      })
      .catch(() => {
        if (isMounted) {
          setCoachStatus({ status: 'local_fallback', has_live_keys: false });
        }
      });
    return () => {
      isMounted = false;
    };
  }, [isOpen]);

  // Cleanup streaming and abort controller only when user explicitly closes the drawer
  useEffect(() => {
    if (!isOpen) {
      abortControllerRef.current?.abort();
      if (streamIntervalRef.current) {
        clearInterval(streamIntervalRef.current);
        streamIntervalRef.current = null;
      }
      isSendingRef.current = false;
      setLoading(false);
    }
  }, [isOpen]);

  // Clean up streaming ticker on unmount
  useEffect(() => {
    return () => {
      if (streamIntervalRef.current) {
        clearInterval(streamIntervalRef.current);
      }
    };
  }, []);

  // Auto-scroll when messages update or loading state changes
  useEffect(() => {
    scrollToBottom('smooth');
  }, [messages.length, loading, scrollToBottom]);

  const handleSend = useCallback(
    async (textToSend, options = {}) => {
      const isDirectText = typeof textToSend === 'string';
      const text = (isDirectText ? textToSend : inputRef.current).trim();
      if (!text) return;
      if (!isDirectText && isSendingRef.current) return;

      // Finish any pending streaming message immediately before starting new query
      if (streamIntervalRef.current) {
        clearInterval(streamIntervalRef.current);
        streamIntervalRef.current = null;
        setMessages(prev =>
          prev.map(m => (m.isStreaming ? { ...m, displayedContent: m.content, isStreaming: false } : m))
        );
      }

      isSendingRef.current = true;
      setLoading(true);
      if (!isDirectText) {
        setInput('');
      }

      abortControllerRef.current?.abort();
      const controller = new AbortController();
      abortControllerRef.current = controller;

      const userMsg = {
        id: `user-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        role: 'user',
        content: text,
        isStreaming: false
      };
      setMessages(prev => [...prev, userMsg]);
      setTimeout(() => scrollToBottom('smooth'), 20);

      const activeChart =
        options.overrideChartContext !== undefined ? options.overrideChartContext : chartContext;
      const activeFilter =
        options.overrideFilterContext !== undefined ? options.overrideFilterContext : filterContext;

      try {
        const res = await sendCoachMessage(
          text,
          activeChart,
          activeFilter,
          threadId,
          controller.signal
        );
        if (res.thread_id) {
          setThreadId(res.thread_id);
        }

        const asstId = res.message_id || `asst-${Date.now()}`;
        const replyText = res.reply || '';

        const asstMsg = {
          id: asstId,
          role: 'assistant',
          content: replyText,
          displayedContent: '',
          isStreaming: true,
          short_tag: res.short_tag,
          decision: res.decision,
          action_card: res.action_card,
          citations: res.citations,
          suggest_intent: res.suggest_intent
        };

        setMessages(prev => [...prev, asstMsg]);
        setLoading(false);

        // Progressive streaming ticker that types out the LLM response
        // while continuously auto-scrolling smoothly so the user doesn't have to scroll
        const stepTimeMs = 20;
        const targetSteps = 45; // ~900ms smooth typing
        const chunkSize = Math.max(3, Math.ceil(replyText.length / targetSteps));
        let cursor = 0;

        streamIntervalRef.current = setInterval(() => {
          cursor += chunkSize;
          if (cursor >= replyText.length) {
            clearInterval(streamIntervalRef.current);
            streamIntervalRef.current = null;
            setMessages(prev =>
              prev.map(m =>
                m.id === asstId ? { ...m, displayedContent: replyText, isStreaming: false } : m
              )
            );
            setTimeout(() => scrollToBottom('smooth'), 60);
          } else {
            const nextChunk = replyText.slice(0, cursor);
            setMessages(prev =>
              prev.map(m => (m.id === asstId ? { ...m, displayedContent: nextChunk } : m))
            );
            scrollToBottom('smooth');
          }
        }, stepTimeMs);
      } catch (err) {
        if (err?.name === 'AbortError') return;
        setLoading(false);
        setMessages(prev => [
          ...prev,
          {
            id: `err-${Date.now()}`,
            role: 'assistant',
            content:
              'Sorry, I am having trouble connecting right now. Your core Trinity firewall and balances remain safe!',
            displayedContent:
              'Sorry, I am having trouble connecting right now. Your core Trinity firewall and balances remain safe!',
            isStreaming: false
          }
        ]);
        setTimeout(() => scrollToBottom('smooth'), 40);
      } finally {
        if (abortControllerRef.current === controller) {
          isSendingRef.current = false;
        }
      }
    },
    [chartContext, filterContext, threadId, scrollToBottom]
  );

  useEffect(() => {
    if (!isOpen || !initialQuery) return;
    const queryText = typeof initialQuery === 'object' ? initialQuery?.text : initialQuery;
    const queryId = typeof initialQuery === 'object' ? initialQuery?.id : queryText;
    const trimmed = (queryText || '').trim();
    if (!trimmed) return;

    if (lastProcessedIdRef.current === queryId) return;
    lastProcessedIdRef.current = queryId;

    const customFilterCtx =
      typeof initialQuery === 'object' ? initialQuery?.filterContext : undefined;
    const customChartId = typeof initialQuery === 'object' ? initialQuery?.chartId : undefined;

    handleSend(trimmed, {
      overrideFilterContext: customFilterCtx !== undefined ? customFilterCtx : filterContext,
      overrideChartContext: customChartId !== undefined ? customChartId : chartContext
    });
    onClearInitialQuery?.();
  }, [isOpen, initialQuery, handleSend, onClearInitialQuery, filterContext, chartContext]);

  if (!isOpen) return null;

  const handleCaptureCoachOrder = async (msgId, intentId, orderId) => {
    setExecutingMsgId(msgId);
    try {
      const res = await captureIntent(intentId, orderId);
      setExecutedResults(prev => ({
        ...prev,
        [msgId]: {
          ok: true,
          data: {
            status: 'settled',
            message: 'PayPal payment captured & ledger settled successfully!',
            paypal_order_id: res.paypal_order_id || orderId,
            paypal_capture_id: res.paypal_capture_id
          }
        }
      }));
      onActionSuccess?.();
    } catch (err) {
      const isUnapproved = err.message?.includes('ORDER_NOT_APPROVED');
      setExecutedResults(prev => ({
        ...prev,
        [msgId]: {
          ok: true,
          data: {
            ...(prev[msgId]?.data || {}),
            status: 'awaiting_approval',
            captureError: isUnapproved
              ? 'PayPal reports buyer approval is not finished yet. Please log into the PayPal window and click Continue/Agree first.'
              : err.message || 'Capture failed'
          }
        }
      }));
    } finally {
      setExecutingMsgId(null);
    }
  };

  const handleOneTapAction = async (msgId, card) => {
    if (!card || executingMsgId) return;

    if (card.action_type === 'open_override' && card.intent_id) {
      if (mode === 'drawer') onClose?.();
      onOpenOverride?.(card.intent_id);
      return;
    }

    setExecutingMsgId(msgId);
    try {
      const res = await executeCoachAction(card, true);

      // Open PayPal checkout approval URL in a new tab if provided
      if (res.approval_url && !res.approval_url.includes('ORDER-MOCK')) {
        window.open(res.approval_url, '_blank', 'noopener,noreferrer');
      }

      setExecutedResults(prev => ({
        ...prev,
        [msgId]: { ok: true, data: res }
      }));
      onActionSuccess?.();
    } catch (err) {
      setExecutedResults(prev => ({
        ...prev,
        [msgId]: { ok: false, error: err.message || 'Execution failed' }
      }));
    } finally {
      setExecutingMsgId(null);
    }
  };

  const contentUI = (
    <div
      className={`bg-slate-900 flex flex-col h-full ${
        mode === 'sidebar'
          ? 'border-l border-slate-800'
          : 'w-full sm:max-w-md shadow-2xl animate-drawer-slide border-l border-slate-800'
      }`}
    >
      {/* Header */}
      <div className="p-3.5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-purple-500/20 border border-purple-500/30 flex items-center justify-center text-purple-400 shadow-sm">
            <Sparkles className="w-3.5 h-3.5" />
          </div>
          <div>
            <div className="flex items-center gap-1.5">
              <h3 className="text-xs font-bold text-white tracking-tight">Financial Coach</h3>
            </div>
            <p className="text-[10px] text-slate-400">Financial Firewall &amp; Intelligent Guidance</p>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {coachStatus && (
            <div
              className={`hidden sm:flex items-center gap-1.5 px-2.5 py-0.5 rounded-full border text-[10px] font-medium transition-colors shadow-sm ${
                coachStatus.status === 'online'
                  ? 'bg-emerald-950/60 border-emerald-800 text-emerald-300'
                  : 'bg-slate-800/80 border-slate-700 text-slate-300'
              }`}
              title={
                coachStatus.status === 'online'
                  ? 'AI Engine Online & Guardrails Active'
                  : 'Deterministic Engine Active'
              }
            >
              <span
                className={`w-1.5 h-1.5 rounded-full ${
                  coachStatus.status === 'online' ? 'bg-emerald-400 animate-pulse' : 'bg-slate-400'
                }`}
              />
              <span className="font-semibold">
                {coachStatus.status === 'online' ? 'AI Engine Active' : 'Deterministic Mode'}
              </span>
            </div>
          )}
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
            title="Close Coach Panel"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Message list with progressive typing & auto-scroll anchor */}
      <div
        ref={messagesContainerRef}
        className="flex-1 overflow-y-auto p-4 space-y-3.5 scroll-smooth"
      >
        {messages.map(msg => {
          const card = msg.action_card;
          const execState = executedResults[msg.id];
          const isExecutingThis = executingMsgId === msg.id;
          const displayText = msg.displayedContent !== undefined ? msg.displayedContent : msg.content;

          return (
            <div
              key={msg.id}
              className={`flex flex-col animate-message-appear ${
                msg.role === 'user' ? 'items-end' : 'items-start'
              }`}
            >
              <div
                className={`max-w-[90%] p-3.5 rounded-2xl text-xs sm:text-sm leading-relaxed transition-all ${
                  msg.role === 'user'
                    ? 'bg-purple-600 text-white rounded-tr-none shadow-md whitespace-pre-line'
                    : 'bg-slate-800/90 text-slate-200 border border-slate-700/60 rounded-tl-none shadow-sm'
                }`}
              >
                {msg.role === 'user' ? (
                  displayText
                ) : (
                  <div>
                    <MarkdownRenderer content={displayText} />
                    {msg.isStreaming && (
                      <span
                        className="inline-block w-1.5 h-3.5 bg-purple-400 ml-1 animate-pulse align-middle rounded-sm"
                        title="Generating response..."
                      />
                    )}
                  </div>
                )}
              </div>

              {/* Citations & Recorded RAG Short-Tag Pills (revealed when typing completes) */}
              {!msg.isStreaming && (msg.short_tag || msg.citations) && (
                <div className="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px] animate-message-appear">
                  {msg.short_tag && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-indigo-950/80 text-indigo-300 border border-indigo-800 font-medium">
                      <Tag className="w-2.5 h-2.5 text-indigo-400" />#{msg.short_tag}
                    </span>
                  )}

                  {msg.citations?.rag_memory?.matched_count > 0 && (
                    <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-950/70 text-amber-300 border border-amber-800/80">
                      <Database className="w-2.5 h-2.5 text-amber-400" />
                      RAG: {msg.citations.rag_memory.matched_count} past tags
                    </span>
                  )}

                  {msg.citations?.deep_ledger && (
                    <>
                      <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-950/80 text-emerald-300 border border-emerald-800">
                        <ShieldCheck className="w-3 h-3 text-emerald-400" />
                        Zero-Sum Verified
                      </span>
                      <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-950/80 text-purple-300 border border-purple-800">
                        <Activity className="w-3 h-3 text-purple-400" />~
                        ${(msg.citations.deep_ledger.daily_burn_rate / 100).toFixed(2)}/day
                      </span>
                      <span className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                        <BarChart2 className="w-3 h-3 text-slate-400" />
                        {msg.citations.deep_ledger.filtered_count} rows analyzed
                      </span>
                    </>
                  )}
                  {msg.citations?.buckets?.length > 0 && !msg.citations?.deep_ledger && (
                    <span className="px-2 py-0.5 rounded-full bg-slate-800/80 text-slate-400 border border-slate-700/60 capitalize">
                      Buckets: {msg.citations.buckets.join(', ')}
                    </span>
                  )}
                </div>
              )}

              {/* Pre-Configured 1-Tap Action Card (revealed when typing completes) */}
              {!msg.isStreaming && card && card.action_type !== 'none' && (
                <div className="mt-2.5 w-full max-w-[90%] p-3 rounded-xl bg-slate-950/90 border border-slate-800 space-y-2.5 shadow-md animate-message-appear">
                  <div className="flex items-center justify-between text-[11px]">
                    <span className="font-bold text-slate-200 flex items-center gap-1.5">
                      {card.is_emergency ? (
                        <>
                          <Zap className="w-3.5 h-3.5 text-amber-400" />
                          <span className="text-amber-300">Emergency Verified &middot; 0s Cooldown</span>
                        </>
                      ) : card.action_type === 'sweep_to_vault' ? (
                        <>
                          <Vault className="w-3.5 h-3.5 text-amber-400" />
                          <span>Zero-Sum Vault Sweep</span>
                        </>
                      ) : (
                        <>
                          <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
                          <span>Pre-Configured 1-Tap Action</span>
                        </>
                      )}
                    </span>
                    <span className="font-mono font-bold text-white">
                      ${(card.amount_cents / 100).toFixed(2)}
                    </span>
                  </div>

                  <div className="flex flex-wrap gap-1.5 text-[10px] text-slate-400">
                    <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 text-slate-300">
                      Tag: <strong>#{card.short_tag}</strong>
                    </span>
                    <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 capitalize">
                      Bucket: <strong>{card.target_bucket}</strong>
                    </span>
                    <span className="px-1.5 py-0.5 rounded bg-slate-900 border border-slate-800 capitalize">
                      Category: <strong>{card.category}</strong>
                    </span>
                  </div>

                  {execState?.ok ? (
                    execState.data?.status === 'awaiting_approval' ? (
                      <div className="p-3 rounded-xl bg-amber-950/60 border border-amber-800 text-amber-200 text-xs space-y-2 animate-in fade-in">
                        <div className="flex items-center gap-1.5 font-bold text-amber-300">
                          <ExternalLink className="w-4 h-4 text-amber-400" />
                          <span>Approve in PayPal Sandbox</span>
                        </div>
                        <p className="text-[11px] text-slate-300 leading-relaxed">
                          PayPal checkout opened in another window. Log into your Sandbox Buyer account, click "Continue" or "Agree", then complete capture.
                        </p>
                        {execState.data.captureError && (
                          <div className="p-2 rounded bg-rose-950/70 border border-rose-900 text-rose-300 text-[11px]">
                            {execState.data.captureError}
                          </div>
                        )}
                        <div className="space-y-1.5 pt-1">
                          <button
                            type="button"
                            onClick={() =>
                              handleCaptureCoachOrder(
                                msg.id,
                                execState.data.intent_id || card.intent_id,
                                execState.data.paypal_order_id
                              )
                            }
                            disabled={isExecutingThis}
                            className="w-full py-2 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-extrabold rounded-lg text-xs flex items-center justify-center gap-1.5 transition-all shadow disabled:opacity-50"
                          >
                            {isExecutingThis ? (
                              <>
                                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                <span>Verifying Completion with PayPal...</span>
                              </>
                            ) : (
                              <>
                                <CheckCircle2 className="w-3.5 h-3.5" />
                                <span>I've Approved on PayPal — Complete &amp; Settle</span>
                              </>
                            )}
                          </button>
                          {execState.data.approval_url && (
                            <button
                              type="button"
                              onClick={() =>
                                window.open(execState.data.approval_url, '_blank', 'noopener,noreferrer')
                              }
                              className="w-full py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-300 rounded-lg text-[11px] flex items-center justify-center gap-1 transition-colors"
                            >
                              <ExternalLink className="w-3 h-3" />
                              <span>Reopen PayPal Window</span>
                            </button>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="p-2.5 rounded-lg bg-emerald-950/60 border border-emerald-800 text-emerald-300 text-xs flex items-start gap-2">
                        <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0 mt-0.5" />
                        <div>
                          <div className="font-bold">{execState.data.message}</div>
                          {execState.data.paypal_order_id && (
                            <div className="text-[10px] text-emerald-400/80 font-mono mt-0.5">
                              Order: {execState.data.paypal_order_id}
                              {execState.data.paypal_capture_id && ` · Capture: ${execState.data.paypal_capture_id}`}
                            </div>
                          )}
                        </div>
                      </div>
                    )
                  ) : (
                    <>
                      {execState?.error && (
                        <div className="text-[11px] text-rose-400 bg-rose-950/50 border border-rose-900 rounded-lg px-2.5 py-1.5">
                          {execState.error}
                        </div>
                      )}
                      <button
                        onClick={() => handleOneTapAction(msg.id, card)}
                        disabled={isExecutingThis}
                        className={`w-full py-2.5 px-3 rounded-lg text-xs font-extrabold flex items-center justify-center gap-1.5 transition-all shadow-sm disabled:opacity-50 ${
                          card.action_type === 'open_override'
                            ? 'bg-rose-600 hover:bg-rose-500 text-white'
                            : 'bg-gradient-to-r from-amber-400 to-amber-500 hover:from-amber-300 hover:to-amber-400 text-slate-950'
                        }`}
                      >
                        {isExecutingThis ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            <span>Executing via Trinity Engine...</span>
                          </>
                        ) : card.action_type === 'open_override' ? (
                          <>
                            <Lock className="w-3.5 h-3.5" />
                            <span>{card.label}</span>
                          </>
                        ) : (
                          <>
                            <span>{card.label}</span>
                            <ExternalLink className="w-3.5 h-3.5" />
                          </>
                        )}
                      </button>
                    </>
                  )}
                </div>
              )}
            </div>
          );
        })}

        {loading && (
          <div className="flex items-center gap-2 text-xs text-purple-300 p-2.5 bg-purple-950/40 border border-purple-900/50 rounded-xl animate-message-appear">
            <Loader2 className="w-4 h-4 animate-spin shrink-0 text-purple-400" />
            <span>Analyzing balances and generating advice...</span>
          </div>
        )}

        {/* Dynamic auto-scroll anchor */}
        <div ref={messagesEndRef} className="h-0 w-0" />
      </div>

      {/* Quick Insight Suggestion Chips */}
      <div className="px-3 py-2 border-t border-slate-800/80 bg-slate-900/60 flex items-center gap-1.5 overflow-x-auto scrollbar-none">
        <button
          type="button"
          onClick={() => handleSend('Explain my Bank double-entry flows and where income moved.')}
          disabled={loading}
          className="text-[11px] px-2.5 py-1 bg-slate-800/80 hover:bg-slate-700 border border-slate-700/60 rounded-full text-slate-300 whitespace-nowrap transition-colors flex items-center gap-1 shrink-0 disabled:opacity-50"
        >
          <span>🏦 Bank double-entry flows</span>
        </button>
        <button
          type="button"
          onClick={() => handleSend('Explain how my rollover streak works and how unspent Daily funds roll over.')}
          disabled={loading}
          className="text-[11px] px-2.5 py-1 bg-slate-800/80 hover:bg-slate-700 border border-slate-700/60 rounded-full text-slate-300 whitespace-nowrap transition-colors flex items-center gap-1 shrink-0 disabled:opacity-50"
        >
          <span>✦ Rollover streak</span>
        </button>
        <button
          type="button"
          onClick={() => handleSend('Why is my Bank Foundation bucket locked by default and how does it protect my bills?')}
          disabled={loading}
          className="text-[11px] px-2.5 py-1 bg-slate-800/80 hover:bg-slate-700 border border-slate-700/60 rounded-full text-slate-300 whitespace-nowrap transition-colors flex items-center gap-1 shrink-0 disabled:opacity-50"
        >
          <span>🔒 Why Bank locked</span>
        </button>
        <button
          type="button"
          onClick={() => handleSend('How does the zero-sum Vault sweep work to automatically build my long-term savings?')}
          disabled={loading}
          className="text-[11px] px-2.5 py-1 bg-slate-800/80 hover:bg-slate-700 border border-slate-700/60 rounded-full text-slate-300 whitespace-nowrap transition-colors flex items-center gap-1 shrink-0 disabled:opacity-50"
        >
          <span>⚡ Vault sweep</span>
        </button>
        <button
          type="button"
          onClick={() => handleSend('Diagnose my daily burn velocity and financial runway across all Trinity buckets.')}
          disabled={loading}
          className="text-[11px] px-2.5 py-1 bg-slate-800/80 hover:bg-slate-700 border border-slate-700/60 rounded-full text-slate-300 whitespace-nowrap transition-colors flex items-center gap-1 shrink-0 disabled:opacity-50"
        >
          <span>📊 Spend velocity</span>
        </button>
        <button
          type="button"
          onClick={() => handleSend('How does the emergency Escape Window work if I need emergency funds from Bank?')}
          disabled={loading}
          className="text-[11px] px-2.5 py-1 bg-slate-800/80 hover:bg-slate-700 border border-slate-700/60 rounded-full text-slate-300 whitespace-nowrap transition-colors flex items-center gap-1 shrink-0 disabled:opacity-50"
        >
          <span>🔥 Escape Window</span>
        </button>
      </div>

      {/* Input area */}
      <div className="p-3 border-t border-slate-800 bg-slate-950/80">
        <form
          onSubmit={(e) => {
            e.preventDefault();
            handleSend();
          }}
          className="flex items-center gap-2"
        >
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={
              filterContext
                ? 'Ask about filtered grid transactions...'
                : 'e.g. "Can I buy $18 takeout?" or "Sweep $25 to vault"'
            }
            className="flex-1 bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-purple-500 transition-colors"
          />
          <button
            type="submit"
            disabled={loading || !input.trim()}
            className="p-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl disabled:opacity-40 transition-colors shadow-sm"
          >
            <Send className="w-3.5 h-3.5" />
          </button>
        </form>
      </div>
    </div>
  );

  if (mode === 'sidebar') {
    return (
      <aside className="w-full lg:w-[420px] h-[calc(100vh-61px)] flex flex-col shadow-2xl transition-all duration-300 ease-in-out shrink-0 sticky top-[61px] overflow-hidden">
        {contentUI}
      </aside>
    );
  }

  return (
    <div
      className="fixed inset-0 z-50 bg-black/75 backdrop-blur-sm flex justify-end animate-backdrop-fade"
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose?.();
        }
      }}
    >
      {contentUI}
    </div>
  );
}
