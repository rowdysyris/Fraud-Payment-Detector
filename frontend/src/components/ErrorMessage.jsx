import { motion, AnimatePresence } from 'framer-motion';
import { normalizeValidationErrors, sanitizeDisplayText } from '../utils/formatters';

export default function ErrorMessage({ message, warnings = [], validationErrors = [] }) {
  const cleanMessage = sanitizeDisplayText(message);
  const visibleWarnings = Array.isArray(warnings) ? warnings.map(sanitizeDisplayText).filter(Boolean).slice(0, 5) : [];
  const visibleValidationErrors = normalizeValidationErrors(validationErrors).filter(Boolean).slice(0, 8);

  return (
    <AnimatePresence>
      {cleanMessage || visibleWarnings.length > 0 || visibleValidationErrors.length > 0 ? (
        <motion.section
          initial={{ opacity: 0, y: -8 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: -8 }}
          className="grid gap-3"
        >
          {cleanMessage ? (
            <div className="rounded-3xl border border-rose-400/30 bg-rose-500/10 p-4 shadow-card">
              <div className="flex gap-3">
                <div className="mt-0.5 grid h-8 w-8 shrink-0 place-items-center rounded-2xl bg-rose-400/15 text-rose-200">!</div>
                <div>
                  <h3 className="font-black text-rose-100">Analysis could not continue</h3>
                  <p className="mt-1 text-sm leading-6 text-rose-100/85">{cleanMessage}</p>
                </div>
              </div>
            </div>
          ) : null}

          {visibleValidationErrors.length > 0 ? (
            <div className="rounded-3xl border border-rose-400/25 bg-rose-500/8 p-4 shadow-card">
              <h3 className="font-black text-rose-100">Validation messages</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-rose-100/85">
                {visibleValidationErrors.map((validationError, index) => (
                  <li key={`${validationError}-${index}`}>{validationError}</li>
                ))}
              </ul>
            </div>
          ) : null}

          {visibleWarnings.length > 0 ? (
            <div className="rounded-3xl border border-amber-400/25 bg-amber-500/10 p-4 shadow-card">
              <h3 className="font-black text-amber-100">Pipeline warnings</h3>
              <ul className="mt-2 list-disc space-y-1 pl-5 text-sm leading-6 text-amber-100/85">
                {visibleWarnings.map((warning, index) => (
                  <li key={`${warning}-${index}`}>{warning}</li>
                ))}
              </ul>
            </div>
          ) : null}
        </motion.section>
      ) : null}
    </AnimatePresence>
  );
}
