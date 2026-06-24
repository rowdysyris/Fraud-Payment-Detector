export function numberOrZero(value) {
  const numericValue = Number(value);
  return Number.isFinite(numericValue) ? numericValue : 0;
}

export function formatNumber(value) {
  return new Intl.NumberFormat('en-IN', {
    maximumFractionDigits: 0,
  }).format(numberOrZero(value));
}

export function formatAmount(value) {
  const numericValue = numberOrZero(value);
  return new Intl.NumberFormat('en-IN', {
    style: 'currency',
    currency: 'INR',
    maximumFractionDigits: numericValue % 1 === 0 ? 0 : 2,
  }).format(numericValue);
}

export function formatPercent(value) {
  const numericValue = numberOrZero(value);
  return `${numericValue.toFixed(numericValue % 1 === 0 ? 0 : 1)}%`;
}

export function compactText(value, maxLength = 110) {
  const text = String(value ?? '').replace(/\s+/g, ' ').trim();
  if (!text) return '—';
  return text.length > maxLength ? `${text.slice(0, maxLength - 1)}…` : text;
}

export function sanitizeDisplayText(value) {
  return String(value ?? '')
    .replace(/Traceback \(most recent call last\):/gi, '')
    .split('\n')
    .filter((line) => !line.trim().startsWith('File "'))
    .join(' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function riskTone(riskLevel) {
  const level = String(riskLevel || '').toLowerCase();
  if (level.includes('critical')) {
    return {
      label: 'Critical',
      border: 'border-rose-400/35',
      bg: 'bg-rose-500/12',
      text: 'text-rose-200',
      dot: 'bg-rose-300',
    };
  }
  if (level.includes('high')) {
    return {
      label: 'High',
      border: 'border-orange-400/35',
      bg: 'bg-orange-500/12',
      text: 'text-orange-200',
      dot: 'bg-orange-300',
    };
  }
  if (level.includes('medium')) {
    return {
      label: 'Medium',
      border: 'border-amber-400/35',
      bg: 'bg-amber-500/12',
      text: 'text-amber-200',
      dot: 'bg-amber-300',
    };
  }
  return {
    label: 'Low',
    border: 'border-cyan-400/25',
    bg: 'bg-cyan-500/10',
    text: 'text-cyan-200',
    dot: 'bg-cyan-300',
  };
}

export function normalizeDownloadLinks(analysis) {
  return analysis?.download_urls || analysis?.download_links || null;
}

export function normalizeAgentSummary(analysis) {
  if (!analysis) return [];
  if (Array.isArray(analysis.agents) && analysis.agents.length > 0) return analysis.agents;
  const summary = analysis.agent_summary || {};
  return Object.entries(summary).map(([name, value]) => ({
    name,
    status: value?.status || 'completed',
    message: value?.message || 'Agent completed.',
    triggered_count: value?.triggered_count || 0,
    warning_count: value?.warning_count || 0,
  }));
}

export function buildRiskDistributionData(analysis) {
  const distribution = analysis?.risk_distribution || analysis?.summary?.risk_distribution || {};
  return ['Low Risk', 'Medium Risk', 'High Risk', 'Critical Risk'].map((name) => ({
    name,
    value: numberOrZero(distribution[name]),
  }));
}

export function normalizeValidationErrors(value) {
  if (!value) return [];
  if (Array.isArray(value)) {
    return value
      .map((item) => {
        if (typeof item === 'string') return sanitizeDisplayText(item);
        if (item?.msg) return sanitizeDisplayText(item.msg);
        if (item?.message) return sanitizeDisplayText(item.message);
        if (item?.error) return sanitizeDisplayText(item.error);
        return sanitizeDisplayText(JSON.stringify(item));
      })
      .filter(Boolean);
  }
  if (typeof value === 'string') return [sanitizeDisplayText(value)].filter(Boolean);
  if (value?.validation_errors) return normalizeValidationErrors(value.validation_errors);
  if (value?.errors) return normalizeValidationErrors(value.errors);
  if (value?.message) return [sanitizeDisplayText(value.message)].filter(Boolean);
  if (value?.error) return [sanitizeDisplayText(value.error)].filter(Boolean);
  return [sanitizeDisplayText(JSON.stringify(value))].filter(Boolean);
}

export function getApiErrorMessage(error) {
  if (!error?.response) {
    if (error?.code === 'ECONNABORTED') {
      return 'The backend took too long to respond. Try a smaller file or check whether the server is still running.';
    }
    if (error?.message === 'Network Error' || error?.code === 'ERR_NETWORK') {
      return 'Cannot reach the SentinelPay AI backend at http://localhost:8000. Start the backend with uvicorn app.main:app --reload and try again.';
    }
    return sanitizeDisplayText(error?.message) || 'Network error. Check that the backend is running and reachable.';
  }

  const status = error.response.status;
  const detail = error.response.data?.detail ?? error.response.data;
  const messages = normalizeValidationErrors(detail);
  const message = messages.join(' ');

  if (status === 400) {
    return message || 'The uploaded file failed validation. Check the required columns and data values.';
  }
  if (status === 404) {
    return message || 'The requested analysis file was not found.';
  }
  if (status >= 500) {
    return message ? `Server error: ${message}` : 'The backend hit a safe internal error while processing the request.';
  }
  return message || 'Unable to analyze the uploaded file.';
}
