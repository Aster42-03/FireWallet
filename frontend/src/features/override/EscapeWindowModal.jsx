import React, { useState, useEffect } from 'react';
import { X, Lock, AlertTriangle, Clock, CheckCircle2, Loader2, Zap, Tag, Copy, Check, Users, ExternalLink, ShieldAlert } from 'lucide-react';
import { submitOverride, checkCooldown, executeIntent, captureIntent, getIntentOrderStatus } from '../../shared/api';
import { useToast } from '../notifications/ToastContext';

export default function EscapeWindowModal({ isOpen, onClose, intentId, onSuccess }) {
  const { showToast } = useToast();
  const [confession, setConfession] = useState('');
  const [isEmergencyMode, setIsEmergencyMode] = useState(false);
  const [loading, setLoading] = useState(false);
  const [overrideData, setOverrideData] = useState(null);
  const [secondsLeft, setSecondsLeft] = useState(180);
  const [readyToExecute, setReadyToExecute] = useState(false);
  const [error, setError] = useState(null);
  const [copiedToken, setCopiedToken] = useState(false);
  const [partnerApproved, setPartnerApproved] = useState(false);
  const [outcomeAlert, setOutcomeAlert] = useState(null);

  // Interactive PayPal Sandbox Approval Loop states
  const [approvalState, setApprovalState] = useState(null); // { orderId, approvalUrl }
  const [capturing, setCapturing] = useState(false);
  const [captureError, setCaptureError] = useState(null);

  const minChars = isEmergencyMode ? 8 : 200;

  useEffect(() => {
    if (!isOpen) {
      setConfession('');
      setIsEmergencyMode(false);
      setOverrideData(null);
      setSecondsLeft(180);
      setReadyToExecute(false);
      setError(null);
      setCopiedToken(false);
      setPartnerApproved(false);
      setOutcomeAlert(null);
      setApprovalState(null);
      setCapturing(false);
      setCaptureError(null);
    }
  }, [isOpen]);

  useEffect(() => {
    let timer;
    if (overrideData && secondsLeft > 0 && !partnerApproved) {
      timer = setInterval(() => {
        setSecondsLeft(prev => {
          if (prev <= 1) {
            clearInterval(timer);
            setReadyToExecute(true);
            return 0;
          }
          return prev - 1;
        });
      }, 1000);
    }
    return () => clearInterval(timer);
  }, [overrideData, secondsLeft, partnerApproved]);

  const handleSubmitConfession = async (e) => {
    e.preventDefault();
    if (confession.trim().length < minChars) {
      setError(
        isEmergencyMode
          ? 'Please briefly describe the medical/safety emergency (at least 8 characters).'
          : `Your confession must be at least ${minChars} characters to ensure deliberate reflection.`
      );
      return;
    }

    setLoading(true);
    setError(null);
    try {
      const res = await submitOverride(intentId, confession);
      setOverrideData(res);
      const cd = res.cooldown_seconds ?? 180;
      setSecondsLeft(cd);
      if (cd <= 0 || res.status === 'approved' || res.is_emergency) {
        setReadyToExecute(true);
        if (res.status === 'approved') setPartnerApproved(true);
      }
    } catch (err) {
      setError(err.message || 'Failed to initiate Escape Window override');
    } finally {
      setLoading(false);
    }
  };

  const handleSimulatePartnerApprove = async () => {
    if (!overrideData?.partner_token) return;
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`/api/v1/partner/approve/${overrideData.partner_token}/decision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ decision: 'approved' }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        throw new Error(data.detail || 'Partner decision failed');
      }
      setPartnerApproved(true);
      setReadyToExecute(true);
      setSecondsLeft(0);
      setOutcomeAlert('Partner approved transaction! 0s cooldown & confession bypassed.');
    } catch (err) {
      setError(err.message || 'Failed to simulate partner approval');
    } finally {
      setLoading(false);
    }
  };

  const handleCancelOverride = async () => {
    if (!overrideData?.id) {
      onClose();
      return;
    }
    setLoading(true);
    try {
      await fetch(`/api/v1/overrides/${overrideData.id}/cancel`, { method: 'POST' });
      setOutcomeAlert('Override cancelled. Alert dispatched to partner.');
      setTimeout(() => {
        onClose();
      }, 1200);
    } catch (err) {
      setError(err.message || 'Failed to cancel override');
    } finally {
      setLoading(false);
    }
  };

  const handleCopyToken = () => {
    if (!overrideData?.partner_token) return;
    navigator.clipboard.writeText(overrideData.partner_token);
    setCopiedToken(true);
    setTimeout(() => setCopiedToken(false), 2000);
  };

  // Auto-poll PayPal Order status while waiting for buyer approval in Escape Window
  useEffect(() => {
    if (!approvalState || capturing || !isOpen || !intentId) return;

    const interval = setInterval(async () => {
      try {
        const statusData = await getIntentOrderStatus(intentId);
        if (statusData.order_status === 'APPROVED') {
          handleConfirmEscapeCapture(approvalState.orderId);
        }
      } catch (err) {
        // Quiet poll fail
      }
    }, 2500);

    return () => clearInterval(interval);
  }, [approvalState, capturing, isOpen, intentId]);

  const handleUnlockAndExecute = async () => {
    setLoading(true);
    setError(null);
    setCaptureError(null);
    setApprovalState(null);

    try {
      await checkCooldown(overrideData.id);
      const returnUrl = `${window.location.origin}/?paypal_return=true&intent_id=${intentId}`;
      const execRes = await executeIntent(intentId, returnUrl);

      if (!execRes.approval_url) {
        throw new Error('PayPal did not return a valid checkout approval URL.');
      }

      // Real interactive PayPal Sandbox flow
      setApprovalState({
        orderId: execRes.paypal_order_id,
        approvalUrl: execRes.approval_url,
      });

      // Open PayPal approval window
      window.open(execRes.approval_url, '_blank', 'noopener,noreferrer');
    } catch (err) {
      setError(err.message || 'Execution failed');
    } finally {
      setLoading(false);
    }
  };

  const handleConfirmEscapeCapture = async (orderIdOverride) => {
    const orderId = orderIdOverride || approvalState?.orderId;
    if (!orderId || !intentId) return;

    setCapturing(true);
    setCaptureError(null);
    try {
      const capRes = await captureIntent(intentId, orderId);
      setOutcomeAlert('Payment settled on PayPal! Outcome alert dispatched to accountability partner.');
      showToast({
        type: 'order_success',
        title: 'Override Payment Settled on PayPal',
        message: 'Escape Window raid captured & settled! Accountability partner notification dispatched.',
        details: `Order: ${orderId} · Capture: ${capRes.paypal_capture_id}`,
        duration: 5000,
      });
      setTimeout(() => {
        onSuccess?.();
        onClose();
      }, 1200);
    } catch (err) {
      const isUnapproved = err.message?.includes('ORDER_NOT_APPROVED');
      setCaptureError(
        isUnapproved
          ? 'PayPal reports buyer approval is not finished yet. Please log into the PayPal window and click Continue/Agree first.'
          : err.message || 'Capture failed'
      );
    } finally {
      setCapturing(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in">
      <div className="bg-slate-900 border border-rose-900/50 rounded-2xl max-w-lg w-full p-6 shadow-2xl relative overflow-hidden">
        {/* Top glow */}
        <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-rose-500 to-amber-500"></div>

        {/* Header */}
        <div className="flex items-start justify-between pb-4 border-b border-slate-800">
          <div>
            <div className="flex items-center gap-2 text-rose-400 font-bold text-sm">
              <AlertTriangle className="w-4 h-4" />
              <span>THE ESCAPE WINDOW</span>
            </div>
            <h3 className="text-xl font-extrabold text-white mt-1">
              {isEmergencyMode ? 'Emergency Zero-Delay Verification' : 'Accountability Dual-Flow Override'}
            </h3>
          </div>
          <button
            onClick={onClose}
            className="p-1 rounded-full text-slate-400 hover:text-white hover:bg-slate-800 transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {error && (
          <div className="mt-4 p-3 bg-rose-950/80 border border-rose-800 rounded-xl text-xs text-rose-300">
            {error}
          </div>
        )}

        {outcomeAlert && (
          <div className="mt-4 p-3 bg-emerald-950/80 border border-emerald-800 rounded-xl text-xs text-emerald-300 flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />
            <span>{outcomeAlert}</span>
          </div>
        )}

        {!overrideData ? (
          <form onSubmit={handleSubmitConfession} className="space-y-4 mt-4">
            {/* Emergency Mode Switcher */}
            <div className="flex items-center justify-between p-3 rounded-xl bg-slate-950 border border-slate-800 text-xs">
              <div className="flex items-center gap-2">
                <Zap className={`w-4 h-4 ${isEmergencyMode ? 'text-amber-400' : 'text-slate-500'}`} />
                <div>
                  <div className="font-bold text-slate-200">Valid Medical / Safety Emergency?</div>
                  <div className="text-[11px] text-slate-400">
                    Verified ER, urgent care, stranded, or shutoff needs get 0s delay.
                  </div>
                </div>
              </div>
              <button
                type="button"
                onClick={() => {
                  setIsEmergencyMode(prev => !prev);
                  setError(null);
                }}
                className={`px-3 py-1.5 rounded-lg font-bold transition-colors ${
                  isEmergencyMode
                    ? 'bg-amber-500 text-slate-950'
                    : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
                }`}
              >
                {isEmergencyMode ? 'Emergency On' : 'Standard'}
              </button>
            </div>

            <p className="text-xs text-slate-300 leading-relaxed">
              {isEmergencyMode
                ? 'Describe the urgent situation below. Our backend guardrail verifies genuine emergencies and unlocks Vault funds with 0s cooldown.'
                : 'Your Trinity rules exist to protect your rent and daily allowance. When your accountability partner approves, transactions unlock immediately with 0s cooldown.'}
            </p>

            <div>
              <div className="flex justify-between text-xs text-slate-400 mb-1">
                <span>
                  {isEmergencyMode ? 'Emergency Reason' : 'Reflection / Reason for Partner'} ({confession.trim().length}/{minChars} chars)
                </span>
                <span className={confession.trim().length >= minChars ? 'text-emerald-400' : 'text-amber-400'}>
                  {confession.trim().length >= minChars
                    ? 'Requirement met'
                    : `${minChars - confession.trim().length} chars needed`}
                </span>
              </div>
              <textarea
                required
                rows={4}
                value={confession}
                onChange={(e) => setConfession(e.target.value)}
                placeholder={
                  isEmergencyMode
                    ? 'e.g. At urgent care clinic needing emergency prescription & x-ray copay...'
                    : 'Describe your purchase reflection for accountability partner review...'
                }
                className="w-full bg-slate-950 border border-slate-700 rounded-xl p-3 text-sm text-white focus:outline-none focus:border-rose-500 transition-colors resize-none"
              />
            </div>

            <button
              type="submit"
              disabled={loading || confession.trim().length < minChars}
              className={`w-full py-3.5 disabled:opacity-40 font-bold rounded-xl flex items-center justify-center gap-2 transition-all ${
                isEmergencyMode
                  ? 'bg-amber-500 hover:bg-amber-400 text-slate-950'
                  : 'bg-rose-600 hover:bg-rose-500 text-white'
              }`}
            >
              {loading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Verifying Override...</span>
                </>
              ) : isEmergencyMode ? (
                <>
                  <Zap className="w-4 h-4" />
                  <span>Verify Emergency (0s Delay)</span>
                </>
              ) : (
                <>
                  <Users className="w-4 h-4" />
                  <span>Dispatch to Partner & Start Escape Window</span>
                </>
              )}
            </button>
          </form>
        ) : (
          /* Cooldown / Partner Approval / Instant Unlock Phase */
          <div className="space-y-4 mt-4 text-center">
            {/* Status Icon */}
            <div
              className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto border ${
                overrideData.is_emergency || partnerApproved
                  ? 'bg-emerald-500/15 border-emerald-500/40 text-emerald-400'
                  : 'bg-amber-500/10 border-amber-500/30 text-amber-400'
              }`}
            >
              {overrideData.is_emergency || partnerApproved ? (
                <CheckCircle2 className="w-7 h-7" />
              ) : (
                <Clock className="w-7 h-7 animate-pulse" />
              )}
            </div>

            <div>
              <h4 className="text-lg font-bold text-white">
                {overrideData.is_emergency
                  ? 'Emergency Verified — Zero Cooldown!'
                  : partnerApproved
                  ? 'Accountability Partner Approved!'
                  : 'Awaiting Accountability Partner Approval'}
              </h4>
              <p className="text-xs text-slate-400 mt-1">
                {overrideData.is_emergency
                  ? 'Genuine emergency verified. Locked Savings Vault is unlocked for immediate settlement.'
                  : partnerApproved
                  ? '0s Cooldown · Confession Bypassed. Your transaction is unlocked.'
                  : 'If partner approves within the window, spend unlocks immediately with 0s cooldown.'}
              </p>
              {overrideData.short_tag && (
                <div className="mt-2 inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full bg-indigo-950 text-indigo-300 border border-indigo-800 text-[11px] font-semibold">
                  <Tag className="w-3 h-3 text-indigo-400" />
                  Recorded Tag: #{overrideData.short_tag}
                </div>
              )}
            </div>

            {/* Partner Token Testing Card */}
            {overrideData.partner_token && !partnerApproved && !overrideData.is_emergency && (
              <div className="p-3 bg-slate-950 border border-slate-800 rounded-xl text-left space-y-2">
                <div className="flex items-center justify-between text-xs">
                  <span className="font-bold text-slate-300 flex items-center gap-1.5">
                    <Users className="w-3.5 h-3.5 text-indigo-400" />
                    Partner Approval Token (Copy for Testing)
                  </span>
                  <button
                    onClick={handleCopyToken}
                    className="flex items-center gap-1 px-2 py-0.5 rounded bg-indigo-900/60 text-indigo-300 hover:bg-indigo-900 text-[11px] transition-colors"
                  >
                    {copiedToken ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                    <span>{copiedToken ? 'Copied!' : 'Copy'}</span>
                  </button>
                </div>
                <div className="font-mono text-[10px] text-slate-400 bg-slate-900 p-2 rounded break-all select-all">
                  {overrideData.partner_token}
                </div>
                <button
                  type="button"
                  onClick={handleSimulatePartnerApprove}
                  disabled={loading}
                  className="w-full py-1.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-bold transition-colors flex items-center justify-center gap-1"
                >
                  <CheckCircle2 className="w-3.5 h-3.5" />
                  <span>Simulate Partner Approval (Test 0s Bypass)</span>
                </button>
              </div>
            )}

            {/* Countdown timer */}
            <div className="py-3 bg-slate-950 border border-slate-800 rounded-2xl">
              <span
                className={`text-3xl font-mono font-extrabold ${
                  overrideData.is_emergency || partnerApproved ? 'text-emerald-400' : 'text-amber-400'
                }`}
              >
                {Math.floor(secondsLeft / 60)}:{(secondsLeft % 60).toString().padStart(2, '0')}
              </span>
              <p className="text-[10px] text-slate-500 mt-0.5 uppercase tracking-wider font-semibold">
                {overrideData.is_emergency || partnerApproved ? 'Zero Delay Applied' : 'Fallback Timer Remaining'}
              </p>
            </div>

            {/* Actions */}
            <div className="space-y-2 pt-1">
              {approvalState ? (
                <div className="p-4 rounded-xl bg-slate-950/90 border border-amber-500/40 space-y-3.5 text-left animate-in fade-in">
                  <div className="flex items-center gap-2">
                    <div className="w-8 h-8 rounded-lg bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
                      <ExternalLink className="w-4 h-4" />
                    </div>
                    <div>
                      <h4 className="text-sm font-bold text-white">Approve in PayPal Sandbox</h4>
                      <p className="text-[11px] text-amber-300">Checkout opened in another window</p>
                    </div>
                  </div>

                  <div className="p-3 rounded-lg bg-slate-900 border border-slate-800 space-y-1.5 text-xs text-slate-300">
                    <p className="font-semibold text-white">Interactive Sandbox Steps:</p>
                    <ol className="list-decimal pl-4 space-y-1 text-slate-400 text-[11px]">
                      <li>Log into PayPal using your <strong>Sandbox Personal Buyer</strong> credentials.</li>
                      <li>Review the transaction and click <strong>"Continue" / "Agree"</strong>.</li>
                      <li>Click <strong>"Complete &amp; Settle"</strong> below (or auto-detect will capture).</li>
                    </ol>
                  </div>

                  {captureError && (
                    <div className="p-2.5 rounded-lg bg-rose-950/60 border border-rose-800 text-xs text-rose-300 flex items-start gap-2">
                      <ShieldAlert className="w-4 h-4 text-rose-400 shrink-0 mt-0.5" />
                      <span className="leading-relaxed">{captureError}</span>
                    </div>
                  )}

                  <div className="space-y-2 pt-1">
                    <button
                      type="button"
                      onClick={() => handleConfirmEscapeCapture()}
                      disabled={capturing}
                      className="w-full py-3 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-slate-950 font-extrabold rounded-xl flex items-center justify-center gap-2 shadow-lg transition-all disabled:opacity-50 text-xs"
                    >
                      {capturing ? (
                        <>
                          <Loader2 className="w-4 h-4 animate-spin" />
                          <span>Verifying Completion with PayPal...</span>
                        </>
                      ) : (
                        <>
                          <CheckCircle2 className="w-4 h-4" />
                          <span>I've Approved on PayPal — Complete &amp; Settle</span>
                        </>
                      )}
                    </button>

                    <button
                      type="button"
                      onClick={() => window.open(approvalState.approvalUrl, '_blank', 'noopener,noreferrer')}
                      className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium rounded-lg text-xs flex items-center justify-center gap-1.5 transition-colors"
                    >
                      <ExternalLink className="w-3.5 h-3.5" />
                      <span>Reopen PayPal Checkout Window</span>
                    </button>
                  </div>
                </div>
              ) : readyToExecute ? (
                <button
                  onClick={handleUnlockAndExecute}
                  disabled={loading}
                  className="w-full py-3.5 bg-emerald-500 hover:bg-emerald-400 text-slate-950 font-bold rounded-xl flex items-center justify-center gap-2 transition-all shadow-lg disabled:opacity-50"
                >
                  {loading ? (
                    <>
                      <Loader2 className="w-5 h-5 animate-spin" />
                      <span>Opening PayPal Sandbox...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle2 className="w-5 h-5" />
                      <span>Proceed to PayPal Sandbox Checkout</span>
                    </>
                  )}
                </button>
              ) : (
                <p className="text-xs text-slate-400 italic">
                  Awaiting partner approval or countdown timer completion.
                </p>
              )}

              <button
                type="button"
                onClick={handleCancelOverride}
                disabled={loading || capturing}
                className="w-full py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold rounded-xl text-xs transition-colors"
              >
                Cancel Override (Notify Partner)
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
