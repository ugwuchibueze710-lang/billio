import { useEffect, useState } from "react";
import { useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import { formatMoney, RECURRENCE_LABELS, categoryLabel } from "../utils/format";
import { statusVisual } from "../utils/statusVisual";
import { useToast } from "../context/ToastContext";
import { TrashIcon, EditIcon } from "../components/icons";
import BillForm from "../components/BillForm";

export default function BillDetail() {
  const { billId } = useParams();
  const [searchParams] = useSearchParams();
  const occurrenceId = searchParams.get("occurrence");
  const navigate = useNavigate();
  const { show } = useToast();

  const [bill, setBill] = useState(null);
  const [occurrences, setOccurrences] = useState([]);
  const [editing, setEditing] = useState(false);
  const [loading, setLoading] = useState(true);

  async function load() {
    const [billRes, occRes] = await Promise.all([
      api.bills.get(billId),
      api.occurrences.list({ per_page: "50" }),
    ]);
    setBill(billRes.bill);
    setOccurrences(occRes.occurrences.filter((o) => o.bill_definition_id === billId));
  }

  useEffect(() => {
    load().finally(() => setLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [billId]);

  async function handleMarkPaid(id) {
    await api.occurrences.markPaid(id);
    show("Marked as paid.", { type: "success" });
    await load();
  }

  async function handleCancel() {
    if (!confirm(`Cancel ${bill.name}? Payment history will be kept.`)) return;
    await api.bills.cancel(billId);
    show("Bill cancelled.", { type: "success" });
    navigate("/");
  }

  if (loading || !bill) {
    return <div className="h-40 animate-pulse rounded-3xl bg-ink-100" />;
  }

  const highlighted = occurrenceId && occurrences.find((o) => o.id === occurrenceId);

  if (editing) {
    return (
      <div>
        <h1 className="mb-6 text-2xl font-bold text-ink-900">Edit {bill.name}</h1>
        <BillForm
          initialValues={{
            name: bill.name,
            amount: bill.default_amount,
            recurrence: bill.recurrence,
            due_date: highlighted?.due_date || occurrences[0]?.due_date || new Date().toISOString().slice(0, 10),
            category: bill.category || "",
            notes: bill.notes || "",
          }}
          submitLabel="Save changes"
          onSubmit={async (values) => {
            await api.bills.update(billId, {
              name: values.name,
              amount: values.amount,
              category: values.category || undefined,
              notes: values.notes || undefined,
              due_date: values.due_date,
            });
            show("Bill updated.", { type: "success" });
            setEditing(false);
            await load();
          }}
        />
      </div>
    );
  }

  return (
    <div>
      <div className="mb-6 flex items-start justify-between">
        <div>
          <h1 className="text-2xl font-bold text-ink-900">{bill.name}</h1>
          <p className="mt-1 text-sm text-ink-500">
            {RECURRENCE_LABELS[bill.recurrence]} {bill.category && `· ${categoryLabel(bill.category)}`}
          </p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setEditing(true)} className="rounded-xl border border-ink-200 p-2.5 text-ink-500 hover:bg-ink-50">
            <EditIcon className="h-4 w-4" />
          </button>
          <button onClick={handleCancel} className="rounded-xl border border-ink-200 p-2.5 text-danger-600 hover:bg-danger-50">
            <TrashIcon className="h-4 w-4" />
          </button>
        </div>
      </div>

      {bill.notes && <p className="mb-6 rounded-2xl bg-ink-50 p-4 text-sm text-ink-600">{bill.notes}</p>}

      <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-ink-500">Occurrences</h2>
      <div className="space-y-3">
        {occurrences.map((occ) => (
          <OccurrenceRow key={occ.id} occurrence={occ} highlighted={occ.id === occurrenceId} onMarkPaid={handleMarkPaid} />
        ))}
      </div>
    </div>
  );
}

function OccurrenceRow({ occurrence, highlighted, onMarkPaid }) {
  const visual = statusVisual(occurrence);
  const Icon = visual.icon;
  const [marking, setMarking] = useState(false);

  return (
    <div className={`flex items-center gap-3 rounded-2xl border p-4 ${visual.cardClass} ${highlighted ? "ring-2 ring-brand-300" : ""}`}>
      <span className={`flex h-9 w-9 items-center justify-center rounded-full ${visual.badgeClass}`}>
        <Icon className="h-4.5 w-4.5" />
      </span>
      <div className="flex-1">
        <p className="font-semibold tabular-nums text-ink-900">{formatMoney(occurrence.amount)}</p>
        <p className="text-xs text-ink-500">{occurrence.status_label}</p>
      </div>
      {occurrence.status !== "paid" && (
        <button
          onClick={async () => {
            setMarking(true);
            try {
              await onMarkPaid(occurrence.id);
            } finally {
              setMarking(false);
            }
          }}
          disabled={marking}
          className="rounded-lg bg-ink-900 px-3 py-2 text-xs font-semibold text-white hover:bg-ink-800 disabled:opacity-50"
        >
          {marking ? "…" : "Mark paid"}
        </button>
      )}
    </div>
  );
}
