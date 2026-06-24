import { motion } from 'framer-motion';

const getValue = (analysis, key) => Number(analysis?.[key] ?? 0);

export default function RiskFunnel3D({ analysis }) {
  const total = getValue(analysis, 'total_transactions');
  const valid = getValue(analysis, 'valid_transactions');
  const suspicious = getValue(analysis, 'suspicious_transactions');
  const high = getValue(analysis, 'high_risk_transactions');
  const critical = getValue(analysis, 'critical_risk_transactions');

  const stages = [
    { label: 'All Transactions', value: total, color: '#22d3ee', width: 420 },
    { label: 'Validated Transactions', value: valid, color: '#38bdf8', width: 360 },
    { label: 'Suspicious Transactions', value: suspicious, color: '#a78bfa', width: 280 },
    { label: 'High-Risk Transactions', value: high, color: '#fb923c', width: 200 },
    { label: 'Critical Fraud Transactions', value: critical, color: '#fb7185', width: 130 },
  ];

  return (
    <motion.div
      initial={{ opacity: 0, y: 14 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-3xl border border-white/10 bg-[rgba(10,18,40,0.75)] p-6 shadow-2xl"
    >
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h2 className="text-3xl font-extrabold text-white">3D Risk Funnel</h2>
          <p className="mt-2 text-lg text-slate-300">
            All Transactions → Critical Fraud Transactions
          </p>
        </div>
        <div className="rounded-full border border-violet-400/30 bg-violet-500/10 px-5 py-2 text-sm font-bold tracking-[0.2em] text-white">
          LIVE PIPELINE
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
        <div className="rounded-[28px] border border-white/10 bg-[#020b26] p-6">
          <svg viewBox="0 0 500 520" className="h-[520px] w-full">
            <defs>
              <filter id="glow">
                <feDropShadow dx="0" dy="0" stdDeviation="8" floodColor="#60a5fa" floodOpacity="0.35" />
              </filter>
            </defs>

            {stages.map((stage, idx) => {
              const centerX = 250;
              const topY = 55 + idx * 85;
              const height = 72;
              const topWidth = stage.width;
              const bottomWidth = idx < stages.length - 1 ? stages[idx + 1].width : 90;

              const x1 = centerX - topWidth / 2;
              const x2 = centerX + topWidth / 2;
              const x3 = centerX + bottomWidth / 2;
              const x4 = centerX - bottomWidth / 2;
              const y2 = topY + height;

              return (
                <g key={stage.label} filter="url(#glow)">
                  <polygon
                    points={`${x1},${topY} ${x2},${topY} ${x3},${y2} ${x4},${y2}`}
                    fill={stage.color}
                    fillOpacity="0.78"
                    stroke={stage.color}
                    strokeWidth="2"
                  />
                  <ellipse
                    cx={centerX}
                    cy={topY}
                    rx={topWidth / 2}
                    ry="18"
                    fill={stage.color}
                    fillOpacity="0.9"
                  />
                  <text
                    x={centerX}
                    y={topY + 8}
                    textAnchor="middle"
                    fill="white"
                    fontSize="16"
                    fontWeight="700"
                  >
                    {stage.label}
                  </text>
                  <text
                    x={centerX}
                    y={topY + 30}
                    textAnchor="middle"
                    fill="white"
                    fontSize="20"
                    fontWeight="900"
                  >
                    {stage.value.toLocaleString()}
                  </text>
                </g>
              );
            })}
          </svg>
        </div>

        <div className="space-y-4">
          {stages.map((stage, i) => {
            const percent = total > 0 ? Math.round((stage.value / total) * 100) : 0;
            return (
              <div
                key={stage.label}
                className="rounded-[28px] border border-white/10 bg-[rgba(18,24,56,0.7)] p-5"
              >
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-4">
                    <div
                      className="flex h-12 w-12 items-center justify-center rounded-full text-lg font-bold text-black"
                      style={{ backgroundColor: stage.color }}
                    >
                      {i + 1}
                    </div>
                    <div>
                      <div className="text-3xl font-extrabold text-white">{stage.label}</div>
                      <div className="text-lg text-slate-400">{percent}% of uploaded transactions</div>
                    </div>
                  </div>
                  <div className="text-5xl font-extrabold text-white">{stage.value.toLocaleString()}</div>
                </div>

                <div className="mt-4 h-3 rounded-full bg-white/10">
                  <div
                    className="h-3 rounded-full"
                    style={{
                      width: `${percent}%`,
                      backgroundColor: stage.color,
                    }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </motion.div>
  );
}