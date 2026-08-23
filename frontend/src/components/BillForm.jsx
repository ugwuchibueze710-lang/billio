import { useState } from "react";
import { CATEGORIES, RECURRENCE_LABELS, MONTH_LABELS, categoryLabel } from "../utils/format";

const DEFAULT_VALUES = {
  name: "",
  amount: "",
  recurrence: "monthly",
  due_date: "",
  day_of_month: "",
  annual_month: "",
  annual_day: "",
  category: "",
  notes: "",
  reference_number: "",
};

export default function BillForm({
  initialValues,
  needsReview = [],
  onSubmit,
  submitLabel = "Add bill",
  extraBanner,
  recurrenceLocked = false,
}) {
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
    if (values.recurrence === "monthly") {
      const day = Number(values.day_of_month);
      if (!values.day_of_month || day < 1 || day > 31) {
        setError("Please enter a day of the month between 1 and 31.");
        return;
      }
    } else if (values.recurrence === "yearly") {
      const month = Number(values.annual_month);
      const day = Number(values.annual_day);
      if (!values.annual_month || !values.annual_day || month < 1 || month > 12 || day < 1 || day > 31) {
        setError("Please enter a month and day for this annual bill.");
        return;
      }
    } else if (!values.due_date) {
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
          Repeats {needsReview.includes("recurrence") && <span className="text-warn-600">— confirm</span>}
        </label>
        {recurrenceLocked ? (
          <>
            <p className="rounded-xl bg-ink-50 px-3.5 py-2.5 text-sm font-medium text-ink-700">
              {RECURRENCE_LABELS[values.recurrence] || values.recurrence}
            </p>
            <p className="mt-1 text-xs text-ink-400">How often a bill repeats can't be changed after it's created.</p>
          </>
        ) : (
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
        )}
      </div>

      {values.recurrence === "monthly" && (
        <div>
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink-400">
            Day of the month {needsReview.includes("day_of_month") && <span className="text-warn-600">— confirm</span>}
          </label>
          <input
            type="number"
            min="1"
            max="31"
            placeholder="e.g. 15"
            value={values.day_of_month}
            onChange={(e) => update("day_of_month", e.target.value)}
            required
            className={fieldClass("day_of_month")}
          />
          <p className="mt-1 text-xs text-ink-400">We'll work out the exact date each month automatically — no year needed.</p>
        </div>
      )}

      {values.recurrence === "yearly" && (
        <div>
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink-400">
            Month and day it's due{" "}
            {(needsReview.includes("month") || needsReview.includes("day_of_month")) && <span className="text-warn-600">— confirm</span>}
          </label>
          <div className="grid grid-cols-2 gap-3">
            <select
              value={values.annual_month}
              onChange={(e) => update("annual_month", e.target.value)}
              required
              className={fieldClass("month")}
            >
              <option value="">Month</option>
              {MONTH_LABELS.map((label, idx) => (
                <option key={label} value={idx + 1}>
                  {label}
                </option>
              ))}
            </select>
            <input
              type="number"
              min="1"
              max="31"
              placeholder="Day"
              value={values.annual_day}
              onChange={(e) => update("annual_day", e.target.value)}
              required
              className={fieldClass("day_of_month")}
            />
          </div>
          <p className="mt-1 text-xs text-ink-400">We'll figure out this year vs. next year automatically — no year needed.</p>
        </div>
      )}

      {(values.recurrence === "weekly" || values.recurrence === "quarterly" || values.recurrence === "none") && (
        <div>
          <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink-400">
            {values.recurrence === "none" ? "Due date" : "Next due date"}{" "}
            {needsReview.includes("due_date") && <span className="text-warn-600">— confirm</span>}
          </label>
          <input type="date" value={values.due_date} onChange={(e) => update("due_date", e.target.value)} required className={fieldClass("due_date")} />
        </div>
      )}

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
        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink-400">
          Invoice / account number (optional)
          {needsReview.includes("reference_number") && <span className="text-warn-600"> — confirm</span>}
        </label>
        <input
          value={values.reference_number || ""}
          onChange={(e) => update("reference_number", e.target.value)}
          maxLength={100}
          placeholder="e.g. account or invoice number, if the bill has one"
          className={fieldClass("reference_number")}
        />
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
