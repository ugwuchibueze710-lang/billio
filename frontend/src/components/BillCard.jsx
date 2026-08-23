import { useState } from "react";
import { Link } from "react-router-dom";
import { formatMoney } from "../utils/format";
import { statusVisual } from "../utils/statusVisual";
import { CheckCircleIcon } from "./icons";

export default function BillCard({ occurrence, onMarkPaid, dense = false }) {
  const [marking, setMarking] = useState(false);
  const [justPaid, setJustPaid] = useState(false);
  const visual = statusVisual(occurrence);
  const Icon = visual.icon;
  const isPaid = occurrence.status === "paid";
  const isUrgent = occurrence.status === "due_today" || occurrence.status === "overdue";

  async function handleMarkPaid(e) {
    e.preventDefault();
    e.stopPropagation();
    if (marking || isPaid) return;
    setMarking(true);
    try {
      await onMarkPaid(occurrence.id);
      setJustPaid(true);
    } finally {
      setMarking(false);
    }
  }

  return (
    <Link
      to={`/bills/${occurrence.bill_definition_id}?occurrence=${occurrence.id}`}
      className={`group relative flex items-center gap-3 overflow-hidden rounded-2xl border p-4 shadow-sm transition-all hover:shadow-md ${visual.cardClass} ${
        justPaid ? "animate-billio-pop" : ""
      }`}
    >
      <span className={`absolute inset-y-0 left-0 w-1 ${visual.accentBar}`} aria-hidden="true" />

      <div className="min-w-0 flex-1 pl-1">
        <div className="flex items-center gap-2">
          <p className="truncate font-semibold text-ink-900">{occurrence.name}</p>
          {occurrence.category && !dense && (
            <span className="hidden rounded-full bg-ink-50 px-2 py-0.5 text-[11px] font-medium text-ink-400 sm:inline">
              {occurrence.category}
            </span>
          )}
        </div>
        <div className="mt-1 flex items-center gap-2">
          <span className="text-lg font-bold tabular-nums text-ink-900">{formatMoney(occurrence.amount)}</span>
          <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-semibold ${visual.badgeClass}`}>
            <Icon className="h-3.5 w-3.5" />
            {occurrence.status_label}
          </span>
        </div>
      </div>

      {!isPaid ? (
        <button
          onClick={handleMarkPaid}
          disabled={marking}
          className={`shrink-0 rounded-xl px-3.5 py-2.5 text-sm font-semibold shadow-sm transition-all active:scale-95 disabled:opacity-60 ${
            isUrgent
              ? "bg-danger-600 text-white hover:bg-danger-700"
              : "bg-ink-900 text-white hover:bg-ink-800"
          }`}
        >
          {marking ? "…" : "Mark paid"}
        </button>
      ) : (
        <CheckCircleIcon className="h-6 w-6 shrink-0 text-good-600" />
      )}
    </Link>
  );
}
