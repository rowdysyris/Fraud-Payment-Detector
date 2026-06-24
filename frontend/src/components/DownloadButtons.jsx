import { motion } from 'framer-motion';
import { buildDownloadUrl } from '../api/client';
import { normalizeDownloadLinks } from '../utils/formatters';

const DOWNLOADS = [
  {
    key: 'fraud_transactions',
    label: 'fraud_transactions.csv',
    description: 'Medium, High, and Critical risk transactions',
  },
  {
    key: 'all_scored',
    label: 'all_transactions_with_fraud_scores.csv',
    description: 'All valid rows with scores and explanations',
  },
  {
    key: 'summary_report',
    label: 'fraud_summary_report.pdf',
    description: 'Manager-friendly executive summary',
  },
];

export default function DownloadButtons({ analysis }) {
  const links = normalizeDownloadLinks(analysis);
  const hasLinks = Boolean(links?.fraud_transactions || links?.all_scored || links?.summary_report);

  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: 0.1 }}
      className="glass-card rounded-[2rem] p-5"
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-black text-white">Download Reports</h2>
          <p className="mt-1 text-sm text-slate-400">Generated files from backend storage.</p>
        </div>
        {analysis?.job_id ? (
          <span className="hidden max-w-[190px] truncate rounded-full border border-slate-600/70 bg-slate-900/70 px-3 py-1 text-xs text-slate-400 sm:inline-block">
            Job {analysis.job_id}
          </span>
        ) : null}
      </div>

      <div className="mt-5 grid gap-3">
        {DOWNLOADS.map((download) => {
          const href = links?.[download.key];
          const enabled = hasLinks && href;
          return (
            <a
              key={download.key}
              href={enabled ? buildDownloadUrl(href) : undefined}
              target="_blank"
              rel="noreferrer"
              aria-disabled={!enabled}
              className={`group rounded-3xl border p-4 transition ${
                enabled
                  ? 'border-cyan-300/25 bg-cyan-400/10 hover:border-cyan-200/60 hover:bg-cyan-400/15'
                  : 'pointer-events-none border-slate-700/70 bg-slate-900/45 opacity-55'
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-black text-white">{download.label}</p>
                  <p className="mt-1 text-xs leading-5 text-slate-400">{download.description}</p>
                </div>
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl border border-cyan-300/20 bg-slate-950/55 text-cyan-200 transition group-hover:scale-105">
                  ↓
                </span>
              </div>
            </a>
          );
        })}
      </div>
    </motion.section>
  );
}
