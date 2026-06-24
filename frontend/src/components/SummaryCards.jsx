import { motion } from 'framer-motion';
import { formatAmount, formatNumber } from '../utils/formatters';

const CARD_CONFIG = [
  {
    label: 'Total transactions',
    key: 'total_transactions',
    accent: 'from-cyan-300 to-sky-400',
    helper: 'Uploaded rows seen by backend',
  },
  {
    label: 'Valid transactions',
    key: 'valid_transactions',
    altKey: 'validated_transactions',
    accent: 'from-blue-300 to-cyan-400',
    helper: 'Rows usable after validation',
  },
  {
    label: 'Suspicious transactions',
    key: 'suspicious_transactions',
    accent: 'from-violet-300 to-fuchsia-400',
    helper: 'Medium, High, and Critical',
  },
  {
    label: 'High-risk transactions',
    key: 'high_risk_transactions',
    accent: 'from-orange-300 to-amber-400',
    helper: 'Needs manual review',
  },
  {
    label: 'Critical-risk transactions',
    key: 'critical_risk_transactions',
    altKey: 'critical_fraud_transactions',
    accent: 'from-rose-300 to-red-400',
    helper: 'Block and escalate candidates',
  },
  {
    label: 'Total amount at risk',
    key: 'total_amount_at_risk',
    accent: 'from-emerald-300 to-cyan-400',
    helper: 'Sum of suspicious amounts',
    currency: true,
  },
];

function getMetric(summary, config) {
  return summary?.[config.key] ?? summary?.[config.altKey] ?? 0;
}

export default function SummaryCards({ analysis }) {
  const summary = analysis?.summary || analysis || {};

  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: 0.05 }}
      className="glass-card rounded-[2rem] p-5"
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-black text-white">Executive Risk Summary</h2>
          <p className="mt-1 text-sm text-slate-400">Core fraud KPIs from the latest backend run.</p>
        </div>
        {analysis?.status ? (
          <span className="rounded-full border border-emerald-300/25 bg-emerald-400/10 px-3 py-1 text-xs font-black uppercase tracking-[0.16em] text-emerald-200">
            {analysis.status}
          </span>
        ) : null}
      </div>

      <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
        {CARD_CONFIG.map((card, index) => {
          const value = getMetric(summary, card);
          return (
            <motion.div
              key={card.label}
              initial={{ opacity: 0, scale: 0.96 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ duration: 0.35, delay: index * 0.04 }}
              className="metric-card overflow-hidden rounded-3xl p-4"
            >
              <div className={`mb-4 h-1.5 w-16 rounded-full bg-gradient-to-r ${card.accent}`} />
              <p className="text-xs font-black uppercase tracking-[0.18em] text-slate-500">{card.label}</p>
              <p className="mt-2 truncate text-3xl font-black text-white">
                {card.currency ? formatAmount(value) : formatNumber(value)}
              </p>
              <p className="mt-2 text-xs leading-5 text-slate-400">{card.helper}</p>
            </motion.div>
          );
        })}
      </div>
    </motion.section>
  );
}
