import { useEffect, useState } from "react";
import { api } from "../api/client";
import BillCard from "../components/BillCard";
import { formatMoney, formatMonthLabel } from "../utils/format";
import { ChevronRightIcon } from "../components/icons";
import { useToast } from "../context/ToastContext";

const STATUS_FILTERS = [
  { value: "", label: "All" },
  { value: "paid", label: "Paid" },
  { value: "unpaid", label: "Unpaid" },
  { value: "overdue", label: "Overdue" },
];

export default function History() {
  const [months, setMonths] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState("");

  useEffect(() => {
    api.history.months().then((r) => setMonths(r.months)).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="h-40 animate-pulse rounded-3xl bg-ink-100" />;

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-ink-900">History</h1>
      <p className="mb-5 text-sm text-ink-500">Browse as far back as your account goes.</p>

      <div className="mb-6 flex gap-2 overflow-x-auto">
        {STATUS_FILTERS.map((f) => (
          <button
            key={f.value}
            onClick={() => setStatusFilter(f.value)}
            className={`shrink-0 rounded-full px-3.5 py-1.5 text-sm font-medium transition ${
              statusFilter === f.value ? "bg-brand-600 text-white" : "bg-ink-100 text-ink-600 hover:bg-ink-200"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {months.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-ink-200 p-8 text-center text-sm text-ink-400">
          No bill history yet.
        </p>
      ) : (
        <div className="space-y-3">
          {months.map((month) => (
            <MonthSection key={month} month={month} statusFilter={statusFilter} />
          ))}
        </div>
      )}
    </div>
  );
}

function MonthSection({ month, statusFilter }) {
  const [open, setOpen] = useState(false);
  const [summary, setSummary] = useState(null);
  const [occurrences, setOccurrences] = useState(null);
  const { show } = useToast();

  useEffect(() => {
    api.history.summary(month).then(setSummary);
  }, [month]);

  async function toggle() {
    const next = !open;
    setOpen(next);
    if (next && occurrences === null) {
      const params = { month };
      if (statusFilter) params.status = statusFilter;
      const res = await api.history.list(params);
      setOccurrences(res.occurrences);
    }
  }

  async function reload() {
    const params = { month };
    if (statusFilter) params.status = statusFilter;
    const res = await api.history.list(params);
    setOccurrences(res.occurrences);
    api.history.summary(month).then(setSummary);
  }

  useEffect(() => {
    if (open) reload();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter]);

  async function handleMarkPaid(id) {
    await api.occurrences.markPaid(id);
    show("Marked as paid.", { type: "success" });
    await reload();
  }

  return (
    <div className="overflow-hidden rounded-2xl border border-ink-100 bg-white shadow-sm">
      <button onClick={toggle} className="flex w-full items-center justify-between p-4 text-left">
        <div>
          <p className="font-bold text-ink-900">{formatMonthLabel(month)}</p>
          {summary && (
            <p className="text-xs text-ink-500">
              {formatMoney(summary.paid_total)} paid of {formatMoney(summary.expected_total)}
              {Number(summary.outstanding_total) > 0 && <span className="text-danger-600"> · {formatMoney(summary.outstanding_total)} outstanding</span>}
            </p>
          )}
        </div>
        <ChevronRightIcon className={`h-4 w-4 text-ink-400 transition-transform ${open ? "rotate-90" : ""}`} />
      </button>

      {open && (
        <div className="space-y-2 border-t border-ink-100 p-4">
          {occurrences === null ? (
            <div className="h-16 animate-pulse rounded-xl bg-ink-100" />
          ) : occurrences.length === 0 ? (
            <p className="py-4 text-center text-sm text-ink-400">No bills match this filter.</p>
          ) : (
            occurrences.map((occ) => <BillCard key={occ.id} occurrence={occ} onMarkPaid={handleMarkPaid} dense />)
          )}
        </div>
      )}
    </div>
  );
}
