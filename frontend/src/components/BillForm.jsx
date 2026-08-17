import { useState } from "react";
import { CATEGORIES, RECURRENCE_LABELS, categoryLabel } from "../utils/format";

const DEFAULT_VALUES = { name: "", amount: "", recurrence: "monthly", due_date: "", category: "", notes: "" };

export default function BillForm({ initialValues, needsReview = [], onSubmit, submitLabel = "Add bill", extraBanner }) {
  const [values, setValues] = useState({ ...DEFAULT_VALUES, ...initialValues });
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);

  function update(field, value) {
    setValues((v) => ({ ...v, [field]: value }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    if (!values.amount || Number(values.amount) <= 0) {
      setError("Please enter an amount greater than zero.");
      return;
    }
    if (!values.due_date) {
      setError("Please enter a due date.");
      return;
    }
    setSubmitting(true);
    try {
      await onSubmit(values);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setSubmitting(false);
    }
  }

  const fieldClass = (field) =>
    `w-full rounded-xl border px-3.5 py-2.5 text-sm outline-none focus:ring-2 ${
      needsReview.includes(field)
        ? "border-warn-300 bg-warn-50 focus:border-warn-400 focus:ring-warn-100"
        : "border-ink-200 focus:border-brand-400 focus:ring-brand-100"
    }`;

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      {extraBanner}

      <div>
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink-400">
          Bill name {needsReview.includes("name") && <span className="text-warn-600">— please confirm</span>}
        </label>
        <input value={values.name} onChange={(e) => update("name", e.target.value)} required maxLength={200} className={fieldClass("name")} />
      </div>

      <div className="grid grid-cols-2 gap-3">
        <div>
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink-400">
            Amount {needsReview.includes("amount") && <span className="text-warn-600">— confirm</span>}
          </label>
          <div className="relative">
            <span className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-sm text-ink-400">$</span>
            <input
              type="number"
              step="0.01"
              min="0.01"
              value={values.amount}
              onChange={(e) => update("amount", e.target.value)}
              required
              className={`${fieldClass("amount")} pl-6`}
            />
          </div>
        </div>
        <div>
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink-400">
            Due date {needsReview.includes("due_date") && <span className="text-warn-600">— confirm</span>}
          </label>
          <input type="date" value={values.due_date} onChange={(e) => update("due_date", e.target.value)} required className={fieldClass("due_date")} />
        </div>
      </div>

      <div>
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink-400">
          Repeats {needsReview.includes("recurrence") && <span className="text-warn-600">— confirm</span>}
        </label>
        <div className="flex flex-wrap gap-2">
          {Object.entries(RECURRENCE_LABELS).map(([value, label]) => (
            <button
              type="button"
              key={value}
              onClick={() => update("recurrence", value)}
              className={`rounded-full px-3.5 py-1.5 text-sm font-medium transition ${
                values.recurrence === value ? "bg-brand-600 text-white" : "bg-ink-50 text-ink-600 hover:bg-ink-100"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </div>

      <div>
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink-400">Category (optional)</label>
        <select
          value={values.category || ""}
          onChange={(e) => update("category", e.target.value)}
          className="w-full rounded-xl border border-ink-200 px-3.5 py-2.5 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
        >
          <option value="">No category</option>
          {CATEGORIES.map((c) => (
            <option key={c} value={c}>
              {categoryLabel(c)}
            </option>
          ))}
        </select>
      </div>

      <div>
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink-400">Notes (optional)</label>
        <textarea
          value={values.notes || ""}
          onChange={(e) => update("notes", e.target.value)}
          rows={2}
          maxLength={2000}
          className="w-full rounded-xl border border-ink-200 px-3.5 py-2.5 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
        />
      </div>

      {error && <p className="text-sm font-medium text-danger-600">{error}</p>}

      <button
        type="submit"
        disabled={submitting}
        className="w-full rounded-xl bg-ink-900 py-3 text-sm font-semibold text-white transition hover:bg-ink-800 disabled:opacity-50"
      >
        {submitting ? "Saving…" : submitLabel}
      </button>
    </form>
  );
}
