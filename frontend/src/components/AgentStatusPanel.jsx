import { motion } from 'framer-motion';
import { normalizeAgentSummary } from '../utils/formatters';

const EXPECTED_AGENTS = [
  'Data Validation Agent',
  'Schema Mapping Agent',
  'Data Cleaning Agent',
  'Amount Anomaly Agent',
  'Velocity Fraud Agent',
  'User Behavior Agent',
  'Merchant Risk Agent',
  'Location Risk Agent',
  'Duplicate Payment Agent',
  'Final Risk Scoring Agent',
  'Recommendation Agent',
];

function statusTone(status) {
  const normalized = String(status || '').toLowerCase();
  if (normalized.includes('fail')) return 'border-rose-400/30 bg-rose-500/10 text-rose-200';
  if (normalized.includes('warning')) return 'border-amber-400/30 bg-amber-500/10 text-amber-200';
  if (normalized.includes('completed')) return 'border-emerald-400/25 bg-emerald-500/10 text-emerald-200';
  return 'border-slate-600 bg-slate-800/60 text-slate-300';
}

function buildAgentList(analysis) {
  const returnedAgents = normalizeAgentSummary(analysis);
  const byName = new Map(returnedAgents.map((agent) => [agent.name, agent]));
  return EXPECTED_AGENTS.map((name) =>
    byName.get(name) || {
      name,
      status: analysis ? 'not_reported' : 'waiting',
      message: analysis ? 'The backend response did not include a status for this agent.' : 'Waiting for dataset upload.',
      triggered_count: 0,
      warning_count: 0,
    },
  );
}

export default function AgentStatusPanel({ analysis }) {
  const agents = buildAgentList(analysis);

  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: 0.08 }}
      className="glass-card rounded-[2rem] p-5"
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <h2 className="text-xl font-black text-white">Agent Status Panel</h2>
          <p className="mt-1 text-sm text-slate-400">Deterministic fraud agents and pipeline health.</p>
        </div>
        <span className="rounded-full border border-cyan-300/25 bg-cyan-400/10 px-3 py-1 text-xs font-black uppercase tracking-[0.16em] text-cyan-200">
          {agents.filter((agent) => String(agent.status).toLowerCase().includes('completed')).length}/{EXPECTED_AGENTS.length}
        </span>
      </div>

      <div className="mt-5 grid max-h-[560px] gap-3 overflow-auto pr-1">
        {agents.map((agent, index) => (
          <motion.div
            key={agent.name}
            initial={{ opacity: 0, x: -10 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.28, delay: index * 0.025 }}
            className="rounded-3xl border border-slate-700/60 bg-slate-950/45 p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <h3 className="truncate text-sm font-black text-white">{agent.name}</h3>
                <p className="mt-1 line-clamp-2 text-xs leading-5 text-slate-400">{agent.message || 'Agent completed.'}</p>
              </div>
              <span className={`shrink-0 rounded-full border px-2.5 py-1 text-[10px] font-black uppercase tracking-[0.14em] ${statusTone(agent.status)}`}>
                {String(agent.status || 'waiting').replaceAll('_', ' ')}
              </span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
              <div className="rounded-2xl bg-slate-900/70 px-3 py-2">
                <p className="text-slate-500">Triggered</p>
                <p className="mt-1 font-black text-white">{agent.triggered_count ?? 0}</p>
              </div>
              <div className="rounded-2xl bg-slate-900/70 px-3 py-2">
                <p className="text-slate-500">Warnings</p>
                <p className="mt-1 font-black text-white">{agent.warning_count ?? 0}</p>
              </div>
            </div>
          </motion.div>
        ))}
      </div>
    </motion.section>
  );
}
