import { useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import BillForm from "../components/BillForm";
import { useToast } from "../context/ToastContext";
import { CameraIcon, PlusIcon, SparkleIcon, TrashIcon } from "../components/icons";
import { formatMoney } from "../utils/format";

const TABS = [
  { key: "manual", label: "Manual", icon: PlusIcon },
  { key: "photo", label: "Photo", icon: CameraIcon },
  { key: "describe", label: "Describe it", icon: SparkleIcon },
];

export default function AddBill() {
  const [params] = useSearchParams();
  const initialTab = params.get("mode") === "photo" ? "photo" : params.get("mode") === "describe" ? "describe" : "manual";
  const [tab, setTab] = useState(initialTab);
  const navigate = useNavigate();
  const { show } = useToast();

  async function createBill(values, documentId) {
    const payload = {
      name: values.name,
      amount: values.amount,
      recurrence: values.recurrence,
      due_date: values.due_date,
      category: values.category || undefined,
      notes: values.notes || undefined,
      document_id: documentId || undefined,
    };
    await api.bills.create(payload);
  }

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-ink-900">Add a bill</h1>
      <p className="mb-6 text-sm text-ink-500">Enter it yourself, snap a photo, or just describe it.</p>

      <div className="mb-6 flex gap-2 rounded-2xl bg-ink-100 p-1">
        {TABS.map(({ key, label, icon: Icon }) => (
          <button
            key={key}
            onClick={() => setTab(key)}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-xl py-2.5 text-sm font-semibold transition ${
              tab === key ? "bg-white text-ink-900 shadow-sm" : "text-ink-500"
            }`}
          >
            <Icon className="h-4 w-4" /> {label}
          </button>
        ))}
      </div>

      {tab === "manual" && (
        <BillForm
          initialValues={{ due_date: new Date().toISOString().slice(0, 10) }}
          onSubmit={async (values) => {
            await createBill(values);
            show("Bill added.", { type: "success" });
            navigate("/");
          }}
        />
      )}

      {tab === "photo" && <PhotoTab onDone={() => navigate("/")} createBill={createBill} />}
      {tab === "describe" && <DescribeTab onDone={() => navigate("/")} createBill={createBill} />}
    </div>
  );
}

function PhotoTab({ onDone, createBill }) {
  const cameraInputRef = useRef(null);
  const [results, setResults] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const { show } = useToast();

  async function handleFiles(fileList) {
    const files = Array.from(fileList);
    if (files.length === 0) return;
    if (files.length > 15) {
      setError("You can upload at most 15 images at once.");
      return;
    }
    setUploading(true);
    setError(null);
    try {
      const formData = new FormData();
      files.forEach((f) => formData.append("images", f));
      const response = await api.ai.extractBillsBatch(formData);
      setResults(
        response.results.map((r) => ({
          documentId: r.document.id,
          aiAvailable: r.ai_available,
          message: r.message,
          proposal: r.proposal,
          removed: false,
        }))
      );
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Upload failed. Please try again.");
    } finally {
      setUploading(false);
    }
  }

  async function confirmAll(finalValuesById) {
    const active = results.filter((r) => !r.removed);
    let succeeded = 0;
    for (const r of active) {
      const values = finalValuesById[r.documentId];
      try {
        await createBill(values, r.documentId);
        succeeded++;
      } catch (err) {
        show(`Couldn't save ${values.name || "a bill"}: ${err.message}`, { type: "error" });
      }
    }
    if (succeeded > 0) {
      show(`Added ${succeeded} bill${succeeded !== 1 ? "s" : ""}.`, { type: "success" });
      onDone();
    }
  }

  if (results) {
    return <BatchReview results={results} setResults={setResults} onConfirmAll={confirmAll} />;
  }

  return (
    <div className="rounded-3xl border border-dashed border-ink-200 bg-white p-8 text-center">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-brand-50 text-brand-600">
        <CameraIcon className="h-7 w-7" />
      </div>
      <h3 className="mt-4 text-lg font-bold text-ink-900">Take a photo of your bill</h3>
      <p className="mx-auto mt-1 max-w-xs text-sm text-ink-500">
        Billio will read the details with AI and let you confirm before anything is saved.
      </p>
      {/* capture="environment" opens the device camera directly rather than
          a file/gallery picker -- this is the only way to add a bill photo,
          per product decision (no upload-from-gallery option). */}
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp,image/heic"
        capture="environment"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      <button
        onClick={() => cameraInputRef.current?.click()}
        disabled={uploading}
        className="mt-5 flex items-center gap-1.5 rounded-xl bg-ink-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-ink-800 disabled:opacity-50 mx-auto"
      >
        <CameraIcon className="h-4 w-4" />
        {uploading ? "Reading bill…" : "Take a photo"}
      </button>
      {error && <p className="mt-3 text-sm font-medium text-danger-600">{error}</p>}
    </div>
  );
}

function BatchReview({ results, setResults, onConfirmAll }) {
  const [editing, setEditing] = useState({});
  const [confirming, setConfirming] = useState(false);

  function remove(documentId) {
    setResults((prev) => prev.map((r) => (r.documentId === documentId ? { ...r, removed: true } : r)));
  }

  function setValues(documentId, values) {
    setEditing((prev) => ({ ...prev, [documentId]: values }));
  }

  const active = results.filter((r) => !r.removed);

  async function handleConfirmAll() {
    setConfirming(true);
    const finalValues = {};
    for (const r of active) {
      finalValues[r.documentId] =
        editing[r.documentId] || {
          name: r.proposal?.name || "",
          amount: r.proposal?.amount || "",
          recurrence: r.proposal?.recurrence || "monthly",
          due_date: r.proposal?.due_date || new Date().toISOString().slice(0, 10),
          category: r.proposal?.category || "",
          notes: "",
        };
    }
    try {
      await onConfirmAll(finalValues);
    } finally {
      setConfirming(false);
    }
  }

  return (
    <div className="space-y-5">
      <p className="text-sm font-semibold text-ink-700">
        We found {active.length} bill{active.length !== 1 ? "s" : ""}. Review each one below, then confirm all at once.
      </p>

      {active.map((r) => (
        <div key={r.documentId} className="rounded-2xl border border-ink-100 bg-white p-4 shadow-sm">
          <div className="mb-3 flex items-center justify-between">
            {r.proposal?.likely_duplicate && (
              <span className="rounded-full bg-warn-100 px-2.5 py-1 text-xs font-semibold text-warn-700">
                Possible duplicate — check before confirming
              </span>
            )}
            <button onClick={() => remove(r.documentId)} className="ml-auto flex items-center gap-1 text-xs font-semibold text-danger-600 hover:underline">
              <TrashIcon className="h-3.5 w-3.5" /> Remove
            </button>
          </div>

          {!r.aiAvailable && (
            <p className="mb-3 rounded-xl bg-warn-50 p-3 text-sm text-warn-700">
              We couldn't read this automatically — please enter it manually.
            </p>
          )}

          <MiniBillEditor
            initial={{
              name: r.proposal?.name || "",
              amount: r.proposal?.amount || "",
              recurrence: r.proposal?.recurrence || "monthly",
              due_date: r.proposal?.due_date || "",
              category: r.proposal?.category || "",
            }}
            needsReview={r.proposal?.needs_review || []}
            onChange={(values) => setValues(r.documentId, values)}
          />
        </div>
      ))}

      {active.length > 0 && (
        <button
          onClick={handleConfirmAll}
          disabled={confirming}
          className="w-full rounded-xl bg-ink-900 py-3 text-sm font-semibold text-white transition hover:bg-ink-800 disabled:opacity-50"
        >
          {confirming ? "Saving…" : `Confirm all (${active.length})`}
        </button>
      )}
    </div>
  );
}

function MiniBillEditor({ initial, needsReview, onChange }) {
  const [values, setValues] = useState(initial);

  function update(field, value) {
    const next = { ...values, [field]: value };
    setValues(next);
    onChange(next);
  }

  const fieldClass = (field) =>
    `w-full rounded-lg border px-3 py-2 text-sm outline-none focus:ring-2 ${
      needsReview.includes(field) ? "border-warn-300 bg-warn-50 focus:border-warn-400 focus:ring-warn-100" : "border-ink-200 focus:border-brand-400 focus:ring-brand-100"
    }`;

  return (
    <div className="grid grid-cols-2 gap-2">
      <input className={`col-span-2 ${fieldClass("name")}`} placeholder="Bill name" value={values.name} onChange={(e) => update("name", e.target.value)} />
      <input className={fieldClass("amount")} placeholder="Amount" type="number" step="0.01" value={values.amount} onChange={(e) => update("amount", e.target.value)} />
      <input className={fieldClass("due_date")} type="date" value={values.due_date} onChange={(e) => update("due_date", e.target.value)} />
      <select className={`col-span-2 ${fieldClass("recurrence")}`} value={values.recurrence} onChange={(e) => update("recurrence", e.target.value)}>
        <option value="none">One-time</option>
        <option value="weekly">Weekly</option>
        <option value="monthly">Monthly</option>
        <option value="quarterly">Quarterly</option>
        <option value="yearly">Yearly</option>
      </select>
    </div>
  );
}

function DescribeTab({ onDone, createBill }) {
  const [text, setText] = useState("");
  const [proposal, setProposal] = useState(null);
  const [needsReview, setNeedsReview] = useState([]);
  const [aiAvailable, setAiAvailable] = useState(true);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const { show } = useToast();

  async function handleParse(e) {
    e.preventDefault();
    if (!text.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await api.ai.parseText(text.trim());
      setAiAvailable(res.ai_available);
      if (res.proposal) {
        setProposal(res.proposal);
        setNeedsReview(res.proposal.needs_review || []);
      } else {
        setError(res.message || "Couldn't understand that — try the manual form instead.");
      }
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  if (proposal) {
    return (
      <BillForm
        initialValues={{
          name: proposal.name || "",
          amount: proposal.amount || "",
          recurrence: proposal.recurrence || "monthly",
          due_date: proposal.due_date || new Date().toISOString().slice(0, 10),
          category: proposal.category || "",
        }}
        needsReview={needsReview}
        submitLabel="Confirm and add bill"
        onSubmit={async (values) => {
          await createBill(values);
          show("Bill added.", { type: "success" });
          onDone();
        }}
      />
    );
  }

  return (
    <form onSubmit={handleParse} className="space-y-4">
      <div className="rounded-2xl border border-ink-100 bg-white p-4 shadow-sm">
        <p className="mb-2 text-sm font-semibold text-ink-700">Describe the bill in plain English</p>
        <textarea
          value={text}
          onChange={(e) => setText(e.target.value)}
          maxLength={500}
          rows={3}
          placeholder='e.g. "Netflix is $17.99 every month on the 20th"'
          className="w-full rounded-xl border border-ink-200 p-3 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
        />
      </div>
      {error && <p className="text-sm font-medium text-danger-600">{error}</p>}
      <button
        type="submit"
        disabled={loading || !text.trim()}
        className="w-full rounded-xl bg-ink-900 py-3 text-sm font-semibold text-white transition hover:bg-ink-800 disabled:opacity-50"
      >
        {loading ? "Thinking…" : "Continue"}
      </button>
    </form>
  );
}
