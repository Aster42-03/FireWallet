/**
 * CoachDrawer - AI Financial Coach Interface
 * ==========================================
 * Dual-mode conversational panel for the Advanced Reasoning AI Coach:
 * 1. 'sidebar': Desktop side-by-side pane alongside AG Grid workbench, keeping the full ledger visible.
 * 2. 'drawer': Mobile slide-over modal accessible from the HUD.
 * 
 * Features:
 * - Telemetry sync: Receives active filters and selected rows via filterContext.
 * - Dynamic diagnostic chips and citations.
 * - One-tap action conversion via suggest_intent.
 */

import React, { useState } from 'react';
import { X, Send, Sparkles, Loader2, ArrowRight, ShieldCheck, Activity, BarChart2 } from 'lucide-react';
import { sendCoachMessage } from '../../shared/api';

export function CoachDrawer({
                              isOpen,
                              onClose,
                              initialQuery = '',
                              chartContext = null,
                              filterContext = null,
                              onSelectSuggestIntent,
                              mode = 'drawer' // 'drawer' (modal overlay) or 'sidebar' (side-by-side pane)
                            }) {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: "Hello! I am your Financial Coach powered by Advanced Reasoning. I can explain your spending velocity, audit double-entry Bank allocations, analyze filtered AG Grid transactions, and evaluate affordability without touching your rent foundation. How can I assist today?"
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  React.useEffect(() => {
    if (initialQuery) {
      handleSend(initialQuery);
    }
  }, [initialQuery]);

  if (!isOpen) return null;

  const handleSend = async (textToSend) => {
    const text = textToSend || input;
    if (!text.trim() || loading) return;

    const userMsg = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: text
    };
    setMessages(prev => [...prev, userMsg]);
    setInput('');
    setLoading(true);

    try {
      const res = await sendCoachMessage(text, chartContext, filterContext);
      const asstMsg = {
        id: res.message_id || `asst-${Date.now()}`,
        role: 'assistant',
        content: res.reply,
        citations: res.citations,
        suggest_intent: res.suggest_intent
      };
      setMessages(prev => [...prev, asstMsg]);
    } catch (err) {
      setMessages(prev => [
        ...prev,
        {
          id: `err-${Date.now()}`,
          role: 'assistant',
          content: "Sorry, I am having trouble connecting right now. Your core Trinity firewall and balances remain safe!"
        }
      ]);
    } finally {
      setLoading(false);
    }
  };

  const contentUI = (
      <div
          className={`bg-slate-900 flex flex-col h-full ${mode === 'sidebar' ? 'border-l border-slate-800' : 'w-full sm:max-w-md shadow-2xl'}`}>
        {/* Header */}
        <div className="p-3.5 border-b border-slate-800 flex items-center justify-between bg-slate-950/60">
          <div className="flex items-center gap-2">
            <div
                className="w-7 h-7 rounded-lg bg-purple-500/20 border border-purple-500/30 flex items-center justify-center text-purple-400">
              <Sparkles className="w-3.5 h-3.5"/>
            </div>
            <div>
              <div className="flex items-center gap-1.5">
                <h3 className="text-xs font-bold text-white tracking-tight">AI Financial Coach</h3>
                {filterContext && (
                    <span
                        className="px-1.5 py-0.2 rounded text-[10px] bg-purple-950 text-purple-300 border border-purple-800">
                  AG Grid Synced
                </span>
                )}
              </div>
              <p className="text-[10px] text-slate-400">Advanced Reasoning & Deep Ledger Audit</p>
            </div>
          </div>
          <button
              onClick={onClose}
              className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
              title="Close Coach Panel"
          >
            <X className="w-4 h-4"/>
          </button>
        </div>

        {/* Message list */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3.5">
          {messages.map(msg => (
              <div
                  key={msg.id}
                  className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
              >
                <div
                    className={`max-w-[90%] p-3.5 rounded-2xl text-xs sm:text-sm leading-relaxed whitespace-pre-line ${
                        msg.role === 'user'
                            ? 'bg-purple-600 text-white rounded-tr-none shadow-md'
                            : 'bg-slate-800/90 text-slate-200 border border-slate-700/60 rounded-tl-none shadow-sm'
                    }`}
                >
                  {msg.content}
                </div>

                {/* Citations tag */}
                {msg.citations && (
                    <div className="mt-1.5 flex flex-wrap gap-1.5 text-[10px]">
                      {msg.citations.deep_ledger && (
                          <>
                    <span
                        className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-emerald-950/80 text-emerald-300 border border-emerald-800">
                      <ShieldCheck className="w-3 h-3 text-emerald-400"/>
                      Zero-Sum Verified
                    </span>
                            <span
                                className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-purple-950/80 text-purple-300 border border-purple-800">
                      <Activity className="w-3 h-3 text-purple-400"/>
                      ~${(msg.citations.deep_ledger.daily_burn_rate / 100).toFixed(2)}/day
                    </span>
                            <span
                                className="flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-800 text-slate-300 border border-slate-700">
                      <BarChart2 className="w-3 h-3 text-slate-400"/>
                              {msg.citations.deep_ledger.filtered_count} rows analyzed
                    </span>
                          </>
                      )}
                      {msg.citations.buckets && !msg.citations.deep_ledger && (
                          <span className="text-slate-400">Envelopes: {msg.citations.buckets.join(', ')}</span>
                      )}
                    </div>
                )}

                {/* Suggest Intent 1-tap deep link */}
                {msg.suggest_intent && (
                    <button
                        onClick={() => {
                          if (mode === 'drawer') onClose();
                          onSelectSuggestIntent?.(msg.suggest_intent);
                        }}
                        className="mt-2 text-xs flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 rounded-full font-semibold transition-all"
                    >
                      <span>Log in Quick Intent (${(msg.suggest_intent.amount / 100).toFixed(2)})</span>
                      <ArrowRight className="w-3.5 h-3.5"/>
                    </button>
                )}
              </div>
          ))}

          {loading && (
              <div
                  className="flex items-center gap-2 text-xs text-purple-400 p-2.5 bg-purple-950/30 border border-purple-900/40 rounded-xl">
                <Loader2 className="w-4 h-4 animate-spin shrink-0"/>
                <span>Reasoning through double-entry ledger and velocity telemetry...</span>
              </div>
          )}
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
                placeholder={filterContext ? "Ask about filtered grid transactions..." : "Ask Coach about cash flow or rules..."}
                className="flex-1 bg-slate-900 border border-slate-700/80 rounded-xl px-3 py-2 text-xs text-white focus:outline-none focus:border-purple-500 transition-colors"
            />
            <button
                type="submit"
                disabled={loading || !input.trim()}
                className="p-2 bg-purple-600 hover:bg-purple-500 text-white rounded-xl disabled:opacity-40 transition-colors shadow-sm"
            >
              <Send className="w-3.5 h-3.5"/>
            </button>
          </form>
        </div>
      </div>
  );

  if (mode === 'sidebar') {
    return (
        <aside
            className="w-full lg:w-[420px] h-[calc(100vh-61px)] flex flex-col shadow-2xl transition-all duration-300 ease-in-out shrink-0 sticky top-[61px] overflow-hidden">
          {contentUI}
        </aside>
    );
  }

  return (
      <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex justify-end animate-in fade-in">
        {contentUI}
      </div>
  );
}
