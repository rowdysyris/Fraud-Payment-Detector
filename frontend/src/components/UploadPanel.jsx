import { useCallback, useMemo, useRef, useState } from 'react';
import { motion } from 'framer-motion';

const ACCEPTED_EXTENSIONS = ['csv', 'xls', 'xlsx'];

function validateFile(file) {
  if (!file) return 'Select a CSV, XLS, or XLSX file.';
  const extension = file.name?.split('.').pop()?.toLowerCase();
  if (!ACCEPTED_EXTENSIONS.includes(extension)) {
    return 'Unsupported file type. Upload a CSV, XLS, or XLSX transaction dataset.';
  }
  return '';
}

export default function UploadPanel({ onUpload, loading, progress = 0 }) {
  const [file, setFile] = useState(null);
  const [localError, setLocalError] = useState('');
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);

  const fileSize = useMemo(() => {
    if (!file?.size) return '';
    const mb = file.size / (1024 * 1024);
    if (mb >= 1) return `${mb.toFixed(2)} MB`;
    return `${(file.size / 1024).toFixed(1)} KB`;
  }, [file]);

  const selectFile = useCallback((selectedFile) => {
    const validationMessage = validateFile(selectedFile);
    setFile(validationMessage ? null : selectedFile);
    setLocalError(validationMessage);
  }, []);

  function handleFileInput(event) {
    selectFile(event.target.files?.[0] || null);
    event.target.value = '';
  }

  function handleDrop(event) {
    event.preventDefault();
    event.stopPropagation();
    if (loading) return;
    setIsDragging(false);
    selectFile(event.dataTransfer.files?.[0] || null);
  }

  function handleSubmit(event) {
    event.preventDefault();
    const validationMessage = validateFile(file);
    if (validationMessage) {
      setLocalError(validationMessage);
      return;
    }
    setLocalError('');
    onUpload(file);
  }

  return (
    <motion.form
      onSubmit={handleSubmit}
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: 0.1 }}
      className="glass-card w-full rounded-[2rem] p-4 md:min-w-[380px] lg:max-w-[440px]"
    >
      <div className="mb-3 flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-bold text-white">Upload transaction dataset</p>
          <p className="mt-1 text-xs text-slate-400">CSV, XLS, or XLSX. Backend validates before scoring.</p>
        </div>
        <span className="rounded-full border border-cyan-300/25 bg-cyan-400/10 px-3 py-1 text-[11px] font-black uppercase tracking-[0.18em] text-cyan-200">
          Secure ingest
        </span>
      </div>

      <button
        type="button"
        onClick={() => {
          if (!loading) inputRef.current?.click();
        }}
        onDragOver={(event) => {
          event.preventDefault();
          if (!loading) setIsDragging(true);
        }}
        onDragLeave={() => setIsDragging(false)}
        onDrop={handleDrop}
        className={`relative flex min-h-[150px] w-full flex-col items-center justify-center overflow-hidden rounded-3xl border border-dashed px-5 py-6 text-center transition ${
          isDragging && !loading
            ? 'border-cyan-300 bg-cyan-400/14 shadow-glow'
            : 'border-slate-600/70 bg-slate-950/55 hover:border-cyan-300/60 hover:bg-cyan-400/8'
        }`}
      >
        <div className="absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-cyan-300/80 to-transparent" />
        <div className="mb-4 grid h-12 w-12 place-items-center rounded-2xl border border-cyan-300/25 bg-cyan-400/10 text-2xl text-cyan-200">
          ↑
        </div>
        <p className="text-sm font-bold text-white">Drag and drop file here</p>
        <p className="mt-1 text-xs text-slate-400">or click to open file picker</p>
        {file ? (
          <div className="mt-4 w-full rounded-2xl border border-slate-700 bg-slate-900/80 px-4 py-3 text-left">
            <p className="truncate text-sm font-bold text-slate-100">{file.name}</p>
            <p className="mt-1 text-xs text-slate-500">{fileSize}</p>
          </div>
        ) : null}
      </button>

      <input ref={inputRef} type="file" accept=".csv,.xlsx,.xls" onChange={handleFileInput} className="hidden" />

      {localError ? (
        <p className="mt-3 rounded-2xl border border-rose-400/25 bg-rose-500/10 px-4 py-3 text-sm font-semibold text-rose-200">
          {localError}
        </p>
      ) : null}

      <button
        type="submit"
        disabled={!file || loading}
        className="mt-4 w-full rounded-2xl bg-gradient-to-r from-cyan-300 via-sky-300 to-violet-300 px-5 py-3.5 text-sm font-black uppercase tracking-[0.18em] text-slate-950 shadow-glow transition hover:scale-[1.01] disabled:cursor-not-allowed disabled:from-slate-700 disabled:via-slate-700 disabled:to-slate-700 disabled:text-slate-400 disabled:shadow-none"
      >
        {loading ? 'Analyzing Dataset' : 'Analyze Dataset'}
      </button>

      {loading ? (
        <div className="mt-4">
          <div className="flex items-center justify-between text-xs text-slate-400">
            <span>Uploading and running agents</span>
            <span>{Math.max(0, Math.min(100, Math.round(progress)))}%</span>
          </div>
          <div className="mt-2 h-2 overflow-hidden rounded-full bg-slate-800">
            <div
              className="h-full rounded-full bg-gradient-to-r from-cyan-300 to-violet-300 transition-all duration-300"
              style={{ width: `${Math.max(8, Math.min(100, progress || 8))}%` }}
            />
          </div>
        </div>
      ) : null}
    </motion.form>
  );
}
