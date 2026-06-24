import { useEffect, useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import { getTransactionDetail } from '../api/client';
import { compactText, formatAmount, riskTone } from '../utils/formatters';
import TransactionDeepDiveModal from './TransactionDeepDiveModal';

const TABLE_COLUMNS = [
  { key: 'transaction_id', label: 'Transaction ID' },
  { key: 'user_id', label: 'User ID' },
  { key: 'amount', label: 'Amount', format: 'amount' },
  { key: 'merchant', label: 'Merchant' },
  { key: 'location', label: 'Location' },
  { key: 'rule_fraud_score', label: 'Rule Score' },
  { key: 'ml_fraud_probability', label: 'ML Probability' },
  { key: 'fraud_score', label: 'Final Fraud Score' },
  { key: 'risk_level', label: 'Risk Level', format: 'risk' },
  { key: 'fraud_pattern', label: 'Pattern' },
  { key: 'fraud_reason', label: 'Reason', wide: true },
  { key: 'recommended_action', label: 'Recommended Action', wide: true },
  { key: 'review_status', label: 'Review Status' },
];

const RISK_FILTERS = [
  'All Risks',
  'Critical Risk',
  'High Risk',
  'Medium Risk',
  'Low Risk',
];

function getRiskOrder(riskLevel) {
  const risk = String(riskLevel || '').toLowerCase();

  if (risk.includes('critical')) return 4;
  if (risk.includes('high')) return 3;
  if (risk.includes('medium')) return 2;
  if (risk.includes('low')) return 1;

  return 0;
}

function getRows(analysis) {
  /*
    Priority:
    1. analysis.transactions = full calculated transaction table
    2. analysis.fraud_table_rows = backend risk table if added later
    3. analysis.sample_flagged_transactions = old 10-row fallback

    This keeps old structure and functionality safe.
  */

  if (Array.isArray(analysis?.transactions) && analysis.transactions.length > 0) {
    return analysis.transactions;
  }

  if (Array.isArray(analysis?.fraud_table_rows) && analysis.fraud_table_rows.length > 0) {
    return analysis.fraud_table_rows;
  }

  if (
    Array.isArray(analysis?.sample_flagged_transactions) &&
    analysis.sample_flagged_transactions.length > 0
  ) {
    return analysis.sample_flagged_transactions;
  }

  return [];
}

function getRiskCounts(rows) {
  const counts = {
    'All Risks': rows.length,
    'Critical Risk': 0,
    'High Risk': 0,
    'Medium Risk': 0,
    'Low Risk': 0,
  };

  rows.forEach((row) => {
    const risk = row?.risk_level || 'Low Risk';
    if (Object.prototype.hasOwnProperty.call(counts, risk)) {
      counts[risk] += 1;
    }
  });

  return counts;
}

function renderCell(row, column) {
  const value = row?.[column.key];

  if (column.format === 'amount') {
    return formatAmount(value);
  }

  if (column.format === 'risk') {
    const tone = riskTone(value);

    return (
      <span
        className={`inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-black ${tone.border} ${tone.bg} ${tone.text}`}
      >
        <span className={`h-2 w-2 rounded-full ${tone.dot}`} />
        {value || 'Low Risk'}
      </span>
    );
  }

  if (['rule_fraud_score', 'ml_fraud_probability', 'fraud_score'].includes(column.key)) {
    const score = Number(value || 0);

    return (
      <span className="font-black text-white">
        {Number.isFinite(score) ? score.toFixed(score % 1 === 0 ? 0 : 1) : '0'}
      </span>
    );
  }

  if (column.wide) {
    return compactText(value, 180);
  }

  return compactText(value, 80);
}

export default function FraudTable({ analysis }) {
  const [rows, setRows] = useState([]);
  const [riskFilter, setRiskFilter] = useState('All Risks');

  const [modalOpen, setModalOpen] = useState(false);
  const [modalLoading, setModalLoading] = useState(false);
  const [modalError, setModalError] = useState('');
  const [modalDetail, setModalDetail] = useState(null);
  const [selectedTransactionId, setSelectedTransactionId] = useState('');

  useEffect(() => {
    setRows(getRows(analysis));
    setRiskFilter('All Risks');
    setModalOpen(false);
    setModalDetail(null);
    setModalError('');
    setSelectedTransactionId('');
  }, [analysis]);

  const sortedRows = useMemo(() => {
    return [...rows].sort((a, b) => {
      const riskDiff = getRiskOrder(b?.risk_level) - getRiskOrder(a?.risk_level);
      if (riskDiff !== 0) return riskDiff;

      return Number(b?.fraud_score || 0) - Number(a?.fraud_score || 0);
    });
  }, [rows]);

  const filteredRows = useMemo(() => {
    if (riskFilter === 'All Risks') {
      return sortedRows;
    }

    return sortedRows.filter((row) => row?.risk_level === riskFilter);
  }, [sortedRows, riskFilter]);

  const riskCounts = useMemo(() => getRiskCounts(rows), [rows]);

  async function handleRowClick(row) {
    const transactionId = row?.transaction_id;
    const jobId = analysis?.job_id;

    if (!jobId || !transactionId) return;

    setSelectedTransactionId(String(transactionId));
    setModalOpen(true);
    setModalLoading(true);
    setModalError('');
    setModalDetail(null);

    try {
      const detail = await getTransactionDetail(jobId, transactionId);
      setModalDetail(detail);
    } catch (detailError) {
      setModalError(detailError.message || 'Could not load transaction detail.');
    } finally {
      setModalLoading(false);
    }
  }

  function handleReviewUpdated(updatedTransaction) {
    const updatedId = updatedTransaction?.transaction_id;

    if (!updatedId) return;

    setRows((currentRows) =>
      currentRows.map((row) =>
        String(row?.transaction_id) === String(updatedId)
          ? {
              ...row,
              review_status: updatedTransaction.review_status || row.review_status,
            }
          : row,
      ),
    );
  }

  return (
    <>
      <motion.section
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.45, delay: 0.12 }}
        className="glass-card rounded-[2rem] p-5"
      >
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <h2 className="text-xl font-black text-white">Fraud Risk Table</h2>
            <p className="mt-1 text-sm text-slate-400">
              Filter transactions by calculated risk level. Click any row to open a transaction-level fraud investigation.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <select
              value={riskFilter}
              onChange={(event) => setRiskFilter(event.target.value)}
              className="rounded-full border border-cyan-300/20 bg-slate-950/80 px-4 py-2 text-sm font-black text-white outline-none transition hover:border-cyan-300/50 focus:border-cyan-300/70"
            >
              {RISK_FILTERS.map((risk) => (
                <option key={risk} value={risk} className="bg-slate-950 text-white">
                  {risk} ({riskCounts[risk] || 0})
                </option>
              ))}
            </select>

            <span className="w-fit rounded-full border border-violet-300/25 bg-violet-500/10 px-3 py-1 text-xs font-black uppercase tracking-[0.16em] text-violet-200">
              {filteredRows.length} shown
            </span>
          </div>
        </div>

        <div className="mt-5 overflow-hidden rounded-3xl border border-slate-700/70 bg-slate-950/50">
          {filteredRows.length === 0 ? (
            <div className="grid min-h-[220px] place-items-center p-8 text-center">
              <div>
                <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-3xl border border-cyan-300/20 bg-cyan-400/10 text-2xl text-cyan-200">
                  ✓
                </div>

                <p className="font-black text-white">No transactions found for this risk filter</p>

                <p className="mt-2 max-w-md text-sm leading-6 text-slate-400">
                  Select another risk level from the dropdown or upload a new dataset.
                </p>
              </div>
            </div>
          ) : (
            <div className="max-h-[560px] overflow-auto">
              <table className="min-w-[1280px] w-full divide-y divide-slate-800 text-left text-sm">
                <thead className="sticky top-0 z-10 bg-slate-950/95 backdrop-blur">
                  <tr>
                    {TABLE_COLUMNS.map((column) => (
                      <th
                        key={column.key}
                        className="whitespace-nowrap px-4 py-4 text-xs font-black uppercase tracking-[0.14em] text-slate-400"
                      >
                        {column.label}
                      </th>
                    ))}
                  </tr>
                </thead>

                <tbody className="divide-y divide-slate-800/80">
                  {filteredRows.map((row, rowIndex) => {
                    const clickable = Boolean(analysis?.job_id && row?.transaction_id);

                    return (
                      <tr
                        key={`${row?.transaction_id || 'row'}-${rowIndex}`}
                        role={clickable ? 'button' : undefined}
                        tabIndex={clickable ? 0 : undefined}
                        onClick={() => clickable && handleRowClick(row)}
                        onKeyDown={(event) => {
                          if (clickable && (event.key === 'Enter' || event.key === ' ')) {
                            event.preventDefault();
                            handleRowClick(row);
                          }
                        }}
                        className={`transition ${
                          clickable
                            ? 'cursor-pointer hover:bg-cyan-400/8 focus:bg-cyan-400/8 focus:outline-none'
                            : ''
                        }`}
                      >
                        {TABLE_COLUMNS.map((column) => (
                          <td
                            key={column.key}
                            className={`px-4 py-4 align-top text-slate-300 ${
                              column.wide ? 'max-w-[340px]' : 'max-w-[220px]'
                            }`}
                          >
                            {renderCell(row, column)}
                          </td>
                        ))}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>
      </motion.section>

      <TransactionDeepDiveModal
        open={modalOpen}
        detail={modalDetail}
        loading={modalLoading}
        error={modalError}
        jobId={analysis?.job_id}
        transactionId={selectedTransactionId}
        onClose={() => setModalOpen(false)}
        onReviewUpdated={handleReviewUpdated}
      />
    </>
  );
}