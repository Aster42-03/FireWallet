import React, { createContext, useContext, useState, useCallback, useEffect } from 'react';
import { CheckCircle2, AlertTriangle, Loader2, X, Zap, ShieldAlert, Check } from 'lucide-react';

const ToastContext = createContext(null);

let globalToastHandler = null;

/**
 * Global helper to show a toast from anywhere (even outside React component tree).
 */
export const showFloatingToast = (toast) => {
  if (globalToastHandler) {
    globalToastHandler(toast);
  }
};

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const dismissToast = useCallback((id) => {
    setToasts((prev) =>
      prev.map((t) => (t.id === id ? { ...t, isExiting: true } : t))
    );
    setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id));
    }, 350);
  }, []);

  const showToast = useCallback(({
    type = 'success', // 'success', 'order_success', 'batch_success', 'processing', 'warning', 'error', 'cancel'
    title,
    message,
    details = null,
    duration = 4500, // 4.5s default auto-dismiss
  }) => {
    const id = `${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const newToast = {
      id,
      type,
      title: title || (type.includes('success') ? 'Transaction Completed' : 'Notification'),
      message,
      details,
      duration,
      createdAt: Date.now(),
      isExiting: false,
    };

    setToasts((prev) => [...prev, newToast]);

    if (duration && duration > 0) {
      setTimeout(() => {
        dismissToast(id);
      }, duration);
    }

    return id;
  }, [dismissToast]);

  useEffect(() => {
    globalToastHandler = showToast;
    if (typeof window !== 'undefined') {
      window.__triggerGlobalToast = showToast;
    }
    return () => {
      if (globalToastHandler === showToast) {
        globalToastHandler = null;
      }
      if (typeof window !== 'undefined' && window.__triggerGlobalToast === showToast) {
        delete window.__triggerGlobalToast;
      }
    };
  }, [showToast]);

  return (
    <ToastContext.Provider value={{ showToast, dismissToast }}>
      {children}

      {/* Floating Top-Right Corner Container */}
      <aside
        aria-label="Notifications"
        className="fixed top-4 right-4 z-[9999] pointer-events-none flex flex-col gap-2.5 max-w-sm sm:max-w-md w-[calc(100vw-2rem)] sm:w-auto"
      >
        {toasts.map((toast) => {
          const isSuccess = toast.type === 'success' || toast.type === 'order_success' || toast.type === 'batch_success';
          const isProcessing = toast.type === 'processing';
          const isCancel = toast.type === 'cancel';
          const isError = toast.type === 'error';
          const isBatch = toast.type === 'batch_success';

          return (
            <div
              key={toast.id}
              role="status"
              className={`pointer-events-auto rounded-2xl p-4 shadow-2xl backdrop-blur-xl border transition-all relative overflow-hidden ${
                toast.isExiting ? 'toast-exit' : 'toast-enter'
              } ${
                isBatch
                  ? 'bg-slate-950/95 border-sky-500/50 text-sky-100 shadow-sky-950/60'
                  : isSuccess
                  ? 'bg-slate-950/95 border-emerald-500/50 text-emerald-100 shadow-emerald-950/60'
                  : isProcessing
                  ? 'bg-slate-950/95 border-amber-500/50 text-amber-100 shadow-amber-950/60'
                  : isCancel
                  ? 'bg-slate-950/95 border-slate-700 text-slate-200 shadow-slate-950/60'
                  : 'bg-slate-950/95 border-rose-500/50 text-rose-100 shadow-rose-950/60'
              }`}
            >
              {/* Subtle accent bar at the top */}
              <div
                className={`absolute top-0 left-0 right-0 h-1 ${
                  isBatch
                    ? 'bg-gradient-to-r from-sky-400 via-teal-400 to-sky-500'
                    : isSuccess
                    ? 'bg-gradient-to-r from-emerald-400 via-teal-400 to-emerald-500'
                    : isProcessing
                    ? 'bg-gradient-to-r from-amber-400 to-amber-500'
                    : isCancel
                    ? 'bg-slate-600'
                    : 'bg-gradient-to-r from-rose-500 to-rose-600'
                }`}
              />

              <div className="flex items-start gap-3">
                {/* Icon Badge */}
                <div
                  className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 mt-0.5 border ${
                    isBatch
                      ? 'bg-sky-500/10 border-sky-500/30 text-sky-400'
                      : isSuccess
                      ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400'
                      : isProcessing
                      ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                      : isCancel
                      ? 'bg-slate-800 border-slate-700 text-slate-400'
                      : 'bg-rose-500/10 border-rose-500/30 text-rose-400'
                  }`}
                >
                  {isBatch ? (
                    <Zap className="w-5 h-5 text-sky-400" />
                  ) : isSuccess ? (
                    <CheckCircle2 className="w-5 h-5 text-emerald-400" />
                  ) : isProcessing ? (
                    <Loader2 className="w-5 h-5 animate-spin text-amber-400" />
                  ) : isCancel ? (
                    <AlertTriangle className="w-5 h-5 text-slate-400" />
                  ) : (
                    <ShieldAlert className="w-5 h-5 text-rose-400" />
                  )}
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0 pr-1">
                  <div className="flex items-center gap-2">
                    <h4 className="text-xs font-bold text-white tracking-tight">
                      {toast.title}
                    </h4>
                    {isSuccess && (
                      <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.2 rounded bg-emerald-950/80 text-emerald-300 border border-emerald-800/60">
                        Settled
                      </span>
                    )}
                    {isBatch && (
                      <span className="text-[10px] font-semibold uppercase tracking-wider px-1.5 py-0.2 rounded bg-sky-950/80 text-sky-300 border border-sky-800/60">
                        PayPal Payouts
                      </span>
                    )}
                  </div>

                  {toast.message && (
                    <p className="text-xs text-slate-300 mt-0.5 leading-relaxed">
                      {toast.message}
                    </p>
                  )}

                  {toast.details && (
                    <div className="mt-1.5 text-[11px] font-mono text-slate-400 bg-slate-900/90 border border-slate-800/80 rounded-lg px-2.5 py-1 select-all break-all">
                      {typeof toast.details === 'object' && toast.details !== null
                        ? Object.entries(toast.details)
                            .map(([k, v]) => `${k}: ${v}`)
                            .join(' · ')
                        : String(toast.details)}
                    </div>
                  )}
                </div>

                {/* Close Button */}
                <button
                  type="button"
                  onClick={() => dismissToast(toast.id)}
                  className="text-slate-400 hover:text-white p-1 rounded-lg hover:bg-slate-800/60 transition-colors shrink-0"
                  title="Dismiss notification"
                >
                  <X className="w-4 h-4" />
                </button>
              </div>

              {/* Progress Countdown Bar */}
              {toast.duration && toast.duration > 0 && !toast.isExiting && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-slate-800/60 overflow-hidden">
                  <div
                    className={`h-full ${
                      isBatch
                        ? 'bg-sky-400'
                        : isSuccess
                        ? 'bg-emerald-400'
                        : isProcessing
                        ? 'bg-amber-400'
                        : isCancel
                        ? 'bg-slate-400'
                        : 'bg-rose-400'
                    }`}
                    style={{
                      animation: `toastProgress ${toast.duration}ms linear forwards`,
                    }}
                  />
                </div>
              )}
            </div>
          );
        })}
      </aside>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) {
    return {
      showToast: showFloatingToast,
      dismissToast: () => {},
    };
  }
  return ctx;
}
