import React, { useState } from 'react';
import { X, Send, Sparkles, Loader2, ArrowRight } from 'lucide-react';
import { sendCoachMessage } from '../../shared/api';

export default function CoachDrawer({
  isOpen,
  onClose,
  initialQuery = '',
  chartContext = null,
  onSelectSuggestIntent
}) {
  const [messages, setMessages] = useState([
    {
      id: 'welcome',
      role: 'assistant',
      content: "Hello! I am your Financial Coach. I can explain your spending trends, simulate whether an expense fits into your Daily or Freedom envelopes, and help you protect your rent foundation. How can I help today?"
    }
  ]);
  const [input, setInput] = useState(initialQuery || '');
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
      const res = await sendCoachMessage(text, chartContext);
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

  return (
    <div className="fixed inset-0 z-50 bg-black/80 backdrop-blur-sm flex justify-end animate-in fade-in">
      <div className="bg-slate-900 border-l border-slate-800 w-full sm:max-w-md h-full flex flex-col shadow-2xl">
        {/* Header */}
        <div className="p-4 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-purple-500/20 border border-purple-500/30 flex items-center justify-center text-purple-400">
              <Sparkles className="w-4 h-4" />
            </div>
            <div>
              <h3 className="text-sm font-bold text-white">Financial Coach</h3>
              <p className="text-[11px] text-slate-400">Advanced Reasoning & Literacy</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Message list */}
        <div className="flex-1 overflow-y-auto p-4 space-y-3">
          {messages.map(msg => (
            <div
              key={msg.id}
              className={`flex flex-col ${msg.role === 'user' ? 'items-end' : 'items-start'}`}
            >
              <div
                className={`max-w-[85%] p-3.5 rounded-2xl text-xs sm:text-sm leading-relaxed ${
                  msg.role === 'user'
                    ? 'bg-purple-600 text-white rounded-tr-none'
                    : 'bg-slate-800 text-slate-200 border border-slate-700/60 rounded-tl-none'
                }`}
              >
                {msg.content}
              </div>

              {/* Citations tag */}
              {msg.citations && (
                <div className="mt-1 flex flex-wrap gap-1 text-[10px] text-slate-400">
                  {msg.citations.buckets && (
                    <span>Buckets checked: {msg.citations.buckets.join(', ')}</span>
                  )}
                  {msg.citations.range && <span>&middot; Range: {msg.citations.range}</span>}
                </div>
              )}

              {/* Suggest Intent 1-tap deep link */}
              {msg.suggest_intent && (
                <button
                  onClick={() => {
                    onClose();
                    onSelectSuggestIntent?.(msg.suggest_intent);
                  }}
                  className="mt-2 text-xs flex items-center gap-1.5 px-3 py-1.5 bg-emerald-500/20 hover:bg-emerald-500/30 border border-emerald-500/40 text-emerald-300 rounded-full font-semibold transition-all"
                >
                  <span>Log in Quick Intent (${(msg.suggest_intent.amount / 100).toFixed(2)})</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          ))}

          {loading && (
            <div className="flex items-center gap-2 text-xs text-purple-400 p-2">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span>Coach is reasoning through your ledger...</span>
            </div>
          )}
        </div>

        {/* Input area */}
        <div className="p-3 border-t border-slate-800 bg-slate-950">
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
              placeholder="Ask anything about your money or charts..."
              className="flex-1 bg-slate-900 border border-slate-700 rounded-xl px-3.5 py-2.5 text-xs sm:text-sm text-white focus:outline-none focus:border-purple-500 transition-colors"
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="p-2.5 bg-purple-600 hover:bg-purple-500 text-white rounded-xl disabled:opacity-50 transition-colors"
            >
              <Send className="w-4 h-4" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}
