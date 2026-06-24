import { useEffect, useMemo, useState } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { updateTransactionReviewStatus } from '../api/client';
import { compactText, formatAmount, riskTone } from '../utils/formatters';

const REVIEW_ACTIONS = [
  { label: 'Mark as Reviewed', value: 'Reviewed' },
  { label: 'Confirm Fraud', value: 'Confirmed Fraud' },
  { label: 'Mark as Safe', value: 'Marked Safe' },
];

const DETAIL_FIELDS = [
  ['transaction_id', 'Transaction ID'],
  ['user_id', 'User ID'],
  ['transaction_time', 'Transaction Time'],
  ['amount', 'Amount', 'amount'],
  ['merchant', 'Merchant'],
  ['location', 'Location'],
  ['payment_method', 'Payment Method'],
  ['rule_fraud_score', 'Rule Fraud Score'],
  ['ml_fraud_probability', 'ML Probability'],
  ['fraud_score', 'Final Fraud Score'],
  ['confidence', 'Confidence'],
  ['review_status', 'Review Status'],
];

function RiskBadge({ level }) {
  const tone = riskTone(level);
  return (
    <span className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-black ${tone.border} ${tone.bg} ${tone.text}`}>
      <span className={`h-2 w-2 rounded-full ${tone.dot}`} />
      {level || 'Low Risk'}
    </span>
  );
}

function formatValue(value, format) {
  if (format === 'amount') return formatAmount(value);
  if (value === null || value === undefined || value === '') return 'N/A';
  if (typeof value === 'number') return Number.isInteger(value) ? value.toString() : value.toFixed(2);
  return String(value);
}

function DetailGrid({ transaction }) {
  return (
    <section className="rounded-3xl border border-slate-700/70 bg-slate-950/50 p-4">
      <h3 className="text-sm font-black uppercase tracking-[0.16em] text-cyan-200">Transaction Details</h3>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {DETAIL_FIELDS.map(([key, label, format]) => (
          <div key={key} className="rounded-2xl border border-slate-800 bg-slate-950/70 p-3">
            <p className="text-[11px] font-black uppercase tracking-[0.14em] text-slate-500">{label}</p>
            <p className="mt-1 break-words text-sm font-bold text-slate-100">{formatValue(transaction?.[key], format)}</p>
          </div>
        ))}
      </div>
    </section>
  );
}

function Timeline({ rows }) {
  const timeline = Array.isArray(rows) ? rows : [];
  return (
    <section className="rounded-3xl border border-slate-700/70 bg-slate-950/50 p-4">
      <h3 className="text-sm font-black uppercase tracking-[0.16em] text-cyan-200">User Transaction Timeline</h3>
      {timeline.length === 0 ? (
        <p className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/70 p-4 text-sm text-slate-400">No recent user timeline available.</p>
      ) : (
        <div className="mt-4 max-h-[330px] overflow-y-auto pr-1">
          <div className="relative space-y-3 before:absolute before:left-3 before:top-2 before:h-[calc(100%-1rem)] before:w-px before:bg-slate-700">
            {timeline.map((item, index) => (
              <div key={`${item.transaction_id || 'timeline'}-${index}`} className={`relative ml-8 rounded-2xl border p-3 ${item.is_selected ? 'border-cyan-300/50 bg-cyan-400/10' : 'border-slate-800 bg-slate-950/65'}`}>
                <span className={`absolute -left-[2.05rem] top-4 h-3 w-3 rounded-full ${item.is_selected ? 'bg-cyan-300 shadow-[0_0_16px_rgba(34,211,238,0.8)]' : 'bg-slate-600'}`} />
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="text-xs font-black text-slate-400">{formatValue(item.transaction_time)}</p>
                    <p className="mt-1 text-sm font-black text-white">{formatAmount(item.amount)} · {compactText(item.merchant, 42)}</p>
                    <p className="mt-1 text-xs text-slate-500">{compactText(item.location, 36)} · {compactText(item.payment_method, 28)}</p>
                  </div>
                  <RiskBadge level={item.risk_level} />
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}

function AgentBreakdown({ rows }) {
  const agents = Array.isArray(rows) ? rows : [];
  return (
    <section className="rounded-3xl border border-slate-700/70 bg-slate-950/50 p-4">
      <h3 className="text-sm font-black uppercase tracking-[0.16em] text-cyan-200">Agent Breakdown</h3>
      <div className="mt-4 grid gap-3 lg:grid-cols-2">
        {agents.map((agent) => (
          <div key={agent.agent_name} className={`rounded-2xl border p-4 ${agent.fired ? 'border-cyan-300/35 bg-cyan-400/10' : 'border-slate-800 bg-slate-950/70'}`}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-black text-white">{agent.agent_name}</p>
                <p className="mt-1 text-xs leading-5 text-slate-400">{agent.reason || 'No signal detected.'}</p>
              </div>
              <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[11px] font-black ${agent.fired ? 'border-cyan-300/35 bg-cyan-400/10 text-cyan-200' : 'border-slate-700 bg-slate-900 text-slate-400'}`}>
                {agent.fired ? 'Fired' : 'Not Fired'}
              </span>
            </div>
            <p className="mt-3 text-xs font-black text-slate-500">Contribution: <span className="text-white">{formatValue(agent.score_contribution)}</span></p>
          </div>
        ))}
      </div>
    </section>
  );
}

function Explanation({ explanation }) {
  const evidence = Array.isArray(explanation?.risk_evidence) ? explanation.risk_evidence : [];
  return (
    <section className="rounded-3xl border border-slate-700/70 bg-slate-950/50 p-4">
      <h3 className="text-sm font-black uppercase tracking-[0.16em] text-cyan-200">Investigation Explanation</h3>
      <div className="mt-4 space-y-4 text-sm leading-6 text-slate-300">
        <p><span className="font-black text-white">Summary:</span> {explanation?.summary || 'No explanation summary returned.'}</p>
        <p><span className="font-black text-white">Why flagged:</span> {explanation?.why_flagged || 'No fraud explanation returned.'}</p>
        <div>
          <p className="font-black text-white">Risk evidence:</p>
          <ul className="mt-2 list-disc space-y-1 pl-5 text-slate-300">
            {evidence.length > 0 ? evidence.map((item, index) => <li key={`${item}-${index}`}>{item}</li>) : <li>No evidence bullets returned.</li>}
          </ul>
        </div>
        <p><span className="font-black text-white">Recommended next step:</span> {explanation?.recommended_next_step || 'Allow transaction'}</p>
        <p className="rounded-2xl border border-amber-300/20 bg-amber-400/10 p-3 text-xs text-amber-100">{explanation?.disclaimer || 'This system flags suspicious transactions for review. It does not prove legal fraud.'}</p>
      </div>
    </section>
  );
}

export default function TransactionDeepDiveModal({ open, detail, loading, error, jobId, transactionId, onClose, onReviewUpdated }) {
  const [actionLoading, setActionLoading] = useState('');
  const [actionError, setActionError] = useState('');
  const [actionMessage, setActionMessage] = useState('');
  const [localDetail, setLocalDetail] = useState(detail);

  useEffect(() => {
    setLocalDetail(detail);
    setActionError('');
    setActionMessage('');
  }, [detail]);

  useEffect(() => {
    if (!open) return undefined;
    function handleKeyDown(event) {
      if (event.key === 'Escape') onClose?.();
    }
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [open, onClose]);

  const transaction = localDetail?.transaction || {};
  const score = Number(transaction?.fraud_score || 0);

  async function handleReview(status) {
    setActionLoading(status);
    setActionError('');
    setActionMessage('');
    try {
      const response = await updateTransactionReviewStatus(jobId, transactionId, status);
      const updatedTransaction = response?.transaction || { ...transaction, review_status: status };
      setLocalDetail((current) => ({
        ...current,
        transaction: { ...(current?.transaction || {}), ...updatedTransaction },
      }));
      onReviewUpdated?.(updatedTransaction);
      setActionMessage(`Review status updated to ${status}.`);
    } catch (reviewError) {
      setActionError(reviewError.message || 'Review status update failed.');
    } finally {
      setActionLoading('');
    }
  }

  return (
    <AnimatePresence>
      {open ? (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/78 p-3 backdrop-blur-md sm:p-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) onClose?.();
          }}
        >
          <motion.div
            initial={{ opacity: 0, y: 18, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 12, scale: 0.98 }}
            transition={{ duration: 0.22 }}
            className="max-h-[92vh] w-full max-w-6xl overflow-hidden rounded-[2rem] border border-slate-700/80 bg-slate-950/95 shadow-[0_24px_80px_rgba(0,0,0,0.55)]"
            role="dialog"
            aria-modal="true"
            aria-label="Transaction fraud investigation details"
          >
            <header className="flex flex-col gap-4 border-b border-slate-800 bg-slate-950/90 p-5 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs font-black uppercase tracking-[0.18em] text-cyan-200">Transaction Deep Dive</p>
                <h2 className="mt-2 break-all text-2xl font-black text-white">{transaction?.transaction_id || transactionId || 'Unknown Transaction'}</h2>
                <div className="mt-3 flex flex-wrap items-center gap-3">
                  <RiskBadge level={transaction?.risk_level} />
                  <span className="rounded-full border border-slate-700 bg-slate-900 px-3 py-1 text-xs font-black text-slate-200">Fraud Score: {Number.isFinite(score) ? score.toFixed(0) : '0'}</span>
                </div>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="rounded-2xl border border-slate-700 bg-slate-900 px-4 py-2 text-sm font-black text-slate-200 transition hover:border-cyan-300/50 hover:text-cyan-100"
                aria-label="Close transaction deep dive"
              >
                Close
              </button>
            </header>

            <div className="max-h-[calc(92vh-126px)] overflow-y-auto p-5">
              {loading ? (
                <div className="grid min-h-[360px] place-items-center text-center">
                  <div>
                    <div className="mx-auto h-12 w-12 animate-spin rounded-full border-4 border-cyan-300/20 border-t-cyan-300" />
                    <p className="mt-4 font-black text-white">Loading transaction investigation...</p>
                  </div>
                </div>
              ) : error ? (
                <div className="rounded-3xl border border-rose-300/25 bg-rose-500/10 p-5 text-sm text-rose-100">{error}</div>
              ) : (
                <div className="space-y-5">
                  <DetailGrid transaction={transaction} />
                  <Timeline rows={localDetail?.user_timeline} />
                  <AgentBreakdown rows={localDetail?.agent_breakdown} />
                  <Explanation explanation={localDetail?.explanation} />

                  <section className="rounded-3xl border border-slate-700/70 bg-slate-950/50 p-4">
                    <h3 className="text-sm font-black uppercase tracking-[0.16em] text-cyan-200">Review Actions</h3>
                    <div className="mt-4 flex flex-wrap gap-3">
                      {REVIEW_ACTIONS.map((action) => (
                        <button
                          key={action.value}
                          type="button"
                          onClick={() => handleReview(action.value)}
                          disabled={Boolean(actionLoading)}
                          className="rounded-2xl border border-cyan-300/25 bg-cyan-400/10 px-4 py-2 text-sm font-black text-cyan-100 transition hover:border-cyan-200/60 hover:bg-cyan-400/18 disabled:cursor-not-allowed disabled:opacity-60"
                        >
                          {actionLoading === action.value ? 'Updating...' : action.label}
                        </button>
                      ))}
                    </div>
                    {actionMessage ? <p className="mt-3 text-sm font-bold text-emerald-300">{actionMessage}</p> : null}
                    {actionError ? <p className="mt-3 text-sm font-bold text-rose-300">{actionError}</p> : null}
                  </section>
                </div>
              )}
            </div>
          </motion.div>
        </motion.div>
      ) : null}
    </AnimatePresence>
  );
}
