import { useEffect, useState } from "react";
import { api } from "../../api/client";
import { formatMoney } from "../../utils/format";

const TYPES = ["", "review", "bug", "improvement", "feature_request", "other"];
const STATUSES = ["new", "reviewing", "planned", "resolved", "dismissed"];

export default function FeedbackAdmin() {
  const [items, setItems] = useState([]);
  const [typeFilter, setTypeFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState("newest");
  const [selected, setSelected] = useState(null);
  const [loading, setLoading] = useState(true);

  async function load() {
    setLoading(true);
    const params = { sort };
    if (typeFilter) params.type = typeFilter;
    if (statusFilter) params.status = statusFilter;
    if (search) params.search = search;
    const res = await api.admin.listFeedback(params);
    setItems(res.feedback);
    setLoading(false);
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [typeFilter, statusFilter, sort]);

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-ink-900">Feedback</h1>
      <p className="mb-6 text-sm text-ink-500">Internal admin view. Never shown to users.</p>

      <div className="mb-4 flex flex-wrap gap-2">
        <select value={typeFilter} onChange={(e) => setTypeFilter(e.target.value)} className="rounded-xl border border-ink-200 px-3 py-2 text-sm">
          {TYPES.map((t) => (
            <option key={t} value={t}>
              {t || "All types"}
            </option>
          ))}
        </select>
        <select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} className="rounded-xl border border-ink-200 px-3 py-2 text-sm">
          <option value="">All statuses</option>
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <select value={sort} onChange={(e) => setSort(e.target.value)} className="rounded-xl border border-ink-200 px-3 py-2 text-sm">
          <option value="newest">Newest first</option>
          <option value="oldest">Oldest first</option>
        </select>
        <form
          onSubmit={(e) => {
            e.preventDefault();
            load();
          }}
          className="flex-1"
        >
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search text…"
            className="w-full rounded-xl border border-ink-200 px-3 py-2 text-sm"
          />
        </form>
      </div>

      {loading ? (
        <div className="h-40 animate-pulse rounded-2xl bg-ink-100" />
      ) : (
        <div className="space-y-2">
          {items.length === 0 && <p className="rounded-xl border border-dashed border-ink-200 p-6 text-center text-sm text-ink-400">No feedback matches.</p>}
          {items.map((f) => (
            <button
              key={f.id}
              onClick={() => setSelected(f)}
              className="flex w-full items-start justify-between rounded-2xl border border-ink-100 bg-white p-4 text-left shadow-sm hover:shadow-md"
            >
              <div className="min-w-0">
                <div className="mb-1 flex items-center gap-2">
                  <span className="rounded-full bg-ink-100 px-2 py-0.5 text-xs font-semibold text-ink-600">{f.type}</span>
                  <span className="rounded-full bg-brand-100 px-2 py-0.5 text-xs font-semibold text-brand-700">{f.status}</span>
                  {f.rating && <span className="text-xs text-warn-600">{"★".repeat(f.rating)}</span>}
                </div>
                <p className="truncate text-sm text-ink-800">{f.message}</p>
                <p className="mt-1 text-xs text-ink-400">
                  {f.user_id} · {new Date(f.created_at).toLocaleDateString()}
                </p>
              </div>
            </button>
          ))}
        </div>
      )}

      {selected && (
        <FeedbackDetailModal
          feedback={selected}
          onClose={() => setSelected(null)}
          onUpdated={(updated) => {
            setItems((prev) => prev.map((i) => (i.id === updated.id ? updated : i)));
            setSelected(updated);
          }}
        />
      )}
    </div>
  );
}

function FeedbackDetailModal({ feedback, onClose, onUpdated }) {
  const [note, setNote] = useState(feedback.admin_note || "");
  const [status, setStatus] = useState(feedback.status);
  const [saving, setSaving] = useState(false);

  async function save() {
    setSaving(true);
    try {
      const res = await api.admin.updateFeedback(feedback.id, { status, admin_note: note });
      onUpdated(res.feedback);
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-ink-950/40 p-4" onClick={onClose}>
      <div onClick={(e) => e.stopPropagation()} className="w-full max-w-md rounded-3xl bg-white p-6 shadow-2xl">
        <div className="mb-4 flex items-center justify-between">
          <span className="rounded-full bg-ink-100 px-2.5 py-1 text-xs font-semibold text-ink-600">{feedback.type}</span>
          <span className="text-xs text-ink-400">{feedback.user_id}</span>
        </div>
        <p className="mb-4 whitespace-pre-wrap rounded-xl bg-ink-50 p-3 text-sm text-ink-800">{feedback.message}</p>

        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink-400">Status</label>
        <select value={status} onChange={(e) => setStatus(e.target.value)} className="mb-4 w-full rounded-xl border border-ink-200 px-3 py-2 text-sm">
          {STATUSES.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>

        <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink-400">Internal note (never shown to user)</label>
        <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={3} className="mb-4 w-full rounded-xl border border-ink-200 p-3 text-sm" />

        <div className="flex gap-2">
          <button onClick={save} disabled={saving} className="flex-1 rounded-xl bg-ink-900 py-2.5 text-sm font-semibold text-white disabled:opacity-50">
            {saving ? "Saving…" : "Save"}
          </button>
          <button onClick={onClose} className="flex-1 rounded-xl border border-ink-200 py-2.5 text-sm font-semibold text-ink-600">
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
