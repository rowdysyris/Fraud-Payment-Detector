import { useMemo, useState } from 'react';
import { motion } from 'framer-motion';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';

import { analyzeTransactions } from './api/client';
import AgentStatusPanel from './components/AgentStatusPanel';
import DownloadButtons from './components/DownloadButtons';
import ErrorMessage from './components/ErrorMessage';
import FraudTable from './components/FraudTable';
import RiskFunnel3D from './components/RiskFunnel3D';
import SummaryCards from './components/SummaryCards';
import UploadPanel from './components/UploadPanel';
import { buildRiskDistributionData, compactText, formatAmount, formatNumber, numberOrZero } from './utils/formatters';

const RISK_COLORS = ['#22d3ee', '#facc15', '#fb923c', '#fb7185'];

function EmptyChart({ title, message }) {
  return (
    <div className="grid h-[260px] place-items-center rounded-3xl border border-slate-700/70 bg-slate-950/45 p-6 text-center">
      <div>
        <p className="font-black text-white">{title}</p>
        <p className="mt-2 max-w-sm text-sm leading-6 text-slate-400">{message}</p>
      </div>
    </div>
  );
}

function ChartCard({ title, subtitle, children }) {
  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: 0.14 }}
      className="glass-card rounded-[2rem] p-5"
    >
      <div>
        <h2 className="text-xl font-black text-white">{title}</h2>
        <p className="mt-1 text-sm text-slate-400">{subtitle}</p>
      </div>
      <div className="mt-5">{children}</div>
    </motion.section>
  );
}

function RiskDistributionChart({ analysis }) {
  const data = buildRiskDistributionData(analysis);
  const hasData = data.some((item) => item.value > 0);

  if (!hasData) {
    return <EmptyChart title="No risk distribution returned" message="The backend response did not include non-zero risk counts for this run." />;
  }

  return (
    <div className="h-[290px] rounded-3xl border border-slate-700/70 bg-slate-950/45 p-3">
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie data={data} dataKey="value" nameKey="name" innerRadius={58} outerRadius={98} paddingAngle={3}>
            {data.map((entry, index) => (
              <Cell key={entry.name} fill={RISK_COLORS[index % RISK_COLORS.length]} />
            ))}
          </Pie>
          <Tooltip
            formatter={(value) => formatNumber(value)}
            contentStyle={{
              background: '#020617',
              border: '1px solid rgba(148, 163, 184, 0.28)',
              borderRadius: '16px',
              color: '#e2e8f0',
            }}
          />
        </PieChart>
      </ResponsiveContainer>
      <div className="-mt-6 grid grid-cols-2 gap-2 px-2 text-xs sm:grid-cols-4">
        {data.map((item, index) => (
          <div key={item.name} className="flex items-center gap-2 text-slate-300">
            <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: RISK_COLORS[index] }} />
            <span>{item.name.replace(' Risk', '')}: {formatNumber(item.value)}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

function TopRiskBarChart({ data, entityKey, emptyTitle, emptyMessage }) {
  const normalized = useMemo(
    () =>
      (Array.isArray(data) ? data : [])
        .slice(0, 5)
        .map((item) => ({
          name: compactText(item?.[entityKey] || 'Unknown', 18),
          average_fraud_score: numberOrZero(item?.average_fraud_score || item?.max_fraud_score),
          suspicious_transactions: numberOrZero(item?.suspicious_transactions),
          amount_at_risk: numberOrZero(item?.amount_at_risk),
        })),
    [data, entityKey],
  );

  if (normalized.length === 0) {
    return <EmptyChart title={emptyTitle} message={emptyMessage} />;
  }

  return (
    <div className="h-[290px] rounded-3xl border border-slate-700/70 bg-slate-950/45 p-3">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={normalized} margin={{ top: 15, right: 20, left: 0, bottom: 12 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(148, 163, 184, 0.16)" />
          <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} />
          <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} axisLine={false} tickLine={false} domain={[0, 100]} />
          <Tooltip
            formatter={(value, name) => {
              if (name === 'amount_at_risk') return formatAmount(value);
              return formatNumber(value);
            }}
            contentStyle={{
              background: '#020617',
              border: '1px solid rgba(148, 163, 184, 0.28)',
              borderRadius: '16px',
              color: '#e2e8f0',
            }}
          />
          <Bar dataKey="average_fraud_score" radius={[10, 10, 0, 0]} fill="#22d3ee" />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

function BackendResponseStrip({ analysis }) {
  if (!analysis) {
    return (
      <div className="grid gap-3 rounded-[2rem] border border-slate-700/60 bg-slate-950/35 p-5 text-sm text-slate-400 md:grid-cols-3">
        <p>Upload a transaction file to start the agentic fraud pipeline.</p>
        <p>The backend maps messy schemas, cleans data, runs agents, and returns reports.</p>
        <p>No generated dashboard metrics are shown before a successful backend analysis.</p>
      </div>
    );
  }

  return (
    <div className="grid gap-3 rounded-[2rem] border border-emerald-400/20 bg-emerald-400/8 p-5 text-sm text-emerald-100/90 md:grid-cols-3">
      <p><span className="font-black text-white">Job ID:</span> {analysis.job_id}</p>
      <p><span className="font-black text-white">File:</span> {analysis.filename || 'uploaded dataset'}</p>
      <p><span className="font-black text-white">Status:</span> {analysis.status || 'completed'}</p>
    </div>
  );
}

function DashboardPreview({ hasError, loading }) {
  const previewItems = [
    {
      title: 'Upload first',
      body: 'Choose a CSV/XLS/XLSX file. The dashboard remains empty until the backend returns a successful analysis.',
    },
    {
      title: 'Backend-driven results',
      body: 'Risk counts, charts, tables, warnings, and downloads are rendered only from the FastAPI response.',
    },
    {
      title: 'Safe failure mode',
      body: 'If validation fails, the UI shows the backend validation message instead of generated metrics.',
    },
  ];

  return (
    <motion.section
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45 }}
      className="glass-card rounded-[2rem] p-6"
    >
      <div className="grid gap-6 lg:grid-cols-[0.95fr_1.05fr] lg:items-center">
        <div>
          <span className={`rounded-full border px-4 py-1.5 text-xs font-black uppercase tracking-[0.2em] ${hasError ? 'border-rose-300/25 bg-rose-500/10 text-rose-200' : 'border-cyan-300/25 bg-cyan-400/10 text-cyan-200'}`}>
            {loading ? 'Analysis running' : hasError ? 'Validation stopped' : 'Dashboard preview'}
          </span>
          <h2 className="mt-5 text-3xl font-black tracking-[-0.04em] text-white sm:text-4xl">
            {hasError ? 'Fix the file issue, then upload again.' : 'Real analysis appears here after upload.'}
          </h2>
          <p className="mt-4 max-w-2xl text-sm leading-7 text-slate-400 sm:text-base">
            SentinelPay AI does not hardcode demo metrics. Once the backend completes successfully, this area changes into the live risk funnel, KPI cards, Recharts analytics, flagged transaction table, and report downloads.
          </p>
        </div>

        <div className="grid gap-3">
          {previewItems.map((item, index) => (
            <div key={item.title} className="metric-card rounded-3xl p-4">
              <div className="flex gap-3">
                <span className="grid h-9 w-9 shrink-0 place-items-center rounded-2xl border border-cyan-300/25 bg-cyan-400/10 text-sm font-black text-cyan-200">
                  {index + 1}
                </span>
                <div>
                  <p className="font-black text-white">{item.title}</p>
                  <p className="mt-1 text-sm leading-6 text-slate-400">{item.body}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    </motion.section>
  );
}

function AnalysisDashboard({ analysis }) {
  return (
    <>
      <SummaryCards analysis={analysis} />

      <div className="grid gap-7 xl:grid-cols-[1.25fr_0.75fr]">
        <RiskFunnel3D analysis={analysis} />
        <div className="grid gap-7">
          <DownloadButtons analysis={analysis} />
          <AgentStatusPanel analysis={analysis} />
        </div>
      </div>

      <div className="grid gap-7 xl:grid-cols-3">
        <ChartCard title="Risk Distribution" subtitle="Count of transactions by assigned risk level.">
          <RiskDistributionChart analysis={analysis} />
        </ChartCard>

        <ChartCard title="Top Risky Merchants" subtitle="Average fraud score for merchants returned by backend.">
          <TopRiskBarChart
            data={analysis?.top_risky_merchants}
            entityKey="merchant"
            emptyTitle="No risky merchants returned"
            emptyMessage="The backend did not return merchant risk rows for this analysis."
          />
        </ChartCard>

        <ChartCard title="Top Risky Users" subtitle="Average fraud score for users returned by backend.">
          <TopRiskBarChart
            data={analysis?.top_risky_users}
            entityKey="user_id"
            emptyTitle="No risky users returned"
            emptyMessage="The backend did not return user risk rows for this analysis."
          />
        </ChartCard>
      </div>

      <FraudTable analysis={analysis} />
    </>
  );
}

export default function App() {
  const [analysis, setAnalysis] = useState(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [progress, setProgress] = useState(0);

  async function handleUpload(file) {
    setError('');
    setAnalysis(null);
    setLoading(true);
    setProgress(8);

    try {
      const data = await analyzeTransactions(file, (event) => {
        if (!event.total) return;
        const uploadPercent = Math.round((event.loaded * 72) / event.total);
        setProgress(Math.max(8, Math.min(82, uploadPercent)));
      });
      setProgress(100);
      setAnalysis(data);
      setError('');
    } catch (uploadError) {
      setAnalysis(null);
      setError(uploadError.message || 'Upload failed. Please check the file and try again.');
      setProgress(0);
    } finally {
      setLoading(false);
      window.setTimeout(() => setProgress(0), 900);
    }
  }

  const warnings = analysis?.warnings || [];
  const validationErrors = analysis?.validation_errors || analysis?.ingestion_metadata?.validation_errors || [];

  return (
    <main className="relative min-h-screen overflow-hidden bg-ink text-slate-100">
      <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(rgba(148,163,184,0.035)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.035)_1px,transparent_1px)] bg-[size:38px_38px]" />
      <div className="pointer-events-none absolute left-1/2 top-0 h-[520px] w-[520px] -translate-x-1/2 rounded-full bg-cyan-400/10 blur-[110px]" />

      <section className="relative mx-auto flex w-full max-w-[1500px] flex-col gap-7 px-4 py-6 sm:px-6 lg:px-8 lg:py-8">
        <motion.header initial={{ opacity: 0, y: -12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }} className="grid gap-6 xl:grid-cols-[1fr_440px] xl:items-end">
          <div>
            <div className="flex flex-wrap items-center gap-3">
              <span className="rounded-full border border-cyan-300/25 bg-cyan-400/10 px-4 py-1.5 text-xs font-black uppercase tracking-[0.22em] text-cyan-200">
                Agentic Fraud Payment Investigator
              </span>
              <span className="rounded-full border border-violet-300/25 bg-violet-500/10 px-4 py-1.5 text-xs font-black uppercase tracking-[0.22em] text-violet-200">
                FastAPI + React
              </span>
            </div>
            <h1 className="mt-5 max-w-4xl text-4xl font-black tracking-[-0.05em] text-white sm:text-6xl lg:text-7xl">
              SentinelPay <span className="bg-gradient-to-r from-cyan-200 via-sky-300 to-violet-300 bg-clip-text text-transparent">AI</span>
            </h1>
            <p className="mt-5 max-w-3xl text-base leading-8 text-slate-300 sm:text-lg">
              Upload a messy transaction CSV or Excel file. The backend validates the data, maps columns, cleans values, runs fraud agents, explains suspicious patterns, and generates downloadable reports.
            </p>
          </div>

          <UploadPanel onUpload={handleUpload} loading={loading} progress={progress} />
        </motion.header>

        <div className="neon-line" />
        <ErrorMessage message={error} warnings={warnings} validationErrors={validationErrors} />
        <BackendResponseStrip analysis={analysis} />

        {analysis ? <AnalysisDashboard analysis={analysis} /> : <DashboardPreview hasError={Boolean(error)} loading={loading} />}
      </section>
    </main>
  );
}
