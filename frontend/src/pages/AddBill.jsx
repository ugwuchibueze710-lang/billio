import { useEffect, useRef, useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { api, ApiError } from "../api/client";
import BillForm from "../components/BillForm";
import { useToast } from "../context/ToastContext";
import { CameraIcon, PlusIcon, SparkleIcon, TrashIcon, UploadIcon } from "../components/icons";
import { formatMoney, MONTH_LABELS } from "../utils/format";

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
      // Only one of these actually applies, depending on recurrence -- the
      // backend picks the right one and ignores the rest (see
      // app/api/bills.py's _resolve_first_due_date). Monthly/yearly bills
      // never need a year from the user; the server works out the actual
      // upcoming calendar date from today.
      day_of_month: values.day_of_month || undefined,
      annual_month: values.annual_month || undefined,
      annual_day: values.annual_day || undefined,
      due_date: values.due_date || undefined,
      category: values.category || undefined,
      notes: values.notes || undefined,
      reference_number: values.reference_number || undefined,
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
  const fileInputRef = useRef(null);
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
      // A single uploaded file can yield MULTIPLE bills (e.g. one photo of
      // a "monthly expenses" summary listing several separate charges), so
      // results are keyed by a synthetic per-bill id, not by document id --
      // several entries can legitimately share the same documentId.
      setResults(
        response.results.map((r) => ({
          key: crypto.randomUUID(),
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

  async function confirmAll(finalValuesByKey) {
    const active = results.filter((r) => !r.removed);
    let succeeded = 0;
    for (const r of active) {
      const values = finalValuesByKey[r.key];
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
      <h3 className="mt-4 text-lg font-bold text-ink-900">Add a photo or PDF of your bill</h3>
      <p className="mx-auto mt-1 max-w-xs text-sm text-ink-500">
        Billio will read the details with AI and let you confirm before anything is saved.
      </p>
      {/* capture="environment" opens the device camera directly rather than
          a file/gallery picker. */}
      <input
        ref={cameraInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      {/* Separate plain file picker (no capture attribute) so PDFs and
          existing photos/screenshots can be uploaded too -- a camera input
          can only ever produce a fresh photo. accept="image/*" offers every
          picture type the OS/browser knows about (JPEG, PNG, HEIC, GIF,
          BMP, TIFF, ...) -- the backend decodes and normalizes whatever
          comes through rather than gating on a fixed list here. */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*,application/pdf"
        multiple
        className="hidden"
        onChange={(e) => handleFiles(e.target.files)}
      />
      <div className="mt-5 flex flex-wrap items-center justify-center gap-3">
        <button
          onClick={() => cameraInputRef.current?.click()}
          disabled={uploading}
          className="flex items-center gap-1.5 rounded-xl bg-ink-900 px-5 py-2.5 text-sm font-semibold text-white hover:bg-ink-800 disabled:opacity-50"
        >
          <CameraIcon className="h-4 w-4" />
          {uploading ? "Reading bill…" : "Take a photo"}
        </button>
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={uploading}
          className="flex items-center gap-1.5 rounded-xl border border-ink-200 bg-white px-5 py-2.5 text-sm font-semibold text-ink-700 hover:bg-ink-50 disabled:opacity-50"
        >
          <UploadIcon className="h-4 w-4" />
          Upload photo or PDF
        </button>
      </div>
      {error && <p className="mt-3 text-sm font-medium text-danger-600">{error}</p>}
    </div>
  );
}

function BatchReview({ results, setResults, onConfirmAll }) {
  const [editing, setEditing] = useState({});
  const [confirming, setConfirming] = useState(false);
  const [sameDayEnabled, setSameDayEnabled] = useState(false);
  const [sameDayValue, setSameDayValue] = useState("");

  function remove(key) {
    setResults((prev) => prev.map((r) => (r.key === key ? { ...r, removed: true } : r)));
  }

  function setValues(key, values) {
    setEditing((prev) => ({ ...prev, [key]: values }));
  }

  const active = results.filter((r) => !r.removed);

  function currentRecurrence(r) {
    return editing[r.key]?.recurrence || r.proposal?.recurrence || "monthly";
  }

  // "Set all monthly bills to the same day" only makes sense (and is only
  // shown) when there's more than one monthly bill in this batch -- e.g.
  // several bills extracted from one "monthly expenses" summary. It never
  // touches annual, weekly, or quarterly bills.
  const monthlyCount = active.filter((r) => currentRecurrence(r) === "monthly").length;

  async function handleConfirmAll() {
    setConfirming(true);
    const finalValues = {};
    for (const r of active) {
      finalValues[r.key] =
        editing[r.key] || {
          name: r.proposal?.name || "",
          amount: r.proposal?.amount || "",
          recurrence: r.proposal?.recurrence || "monthly",
          due_date: r.proposal?.due_date || "",
          day_of_month: r.proposal?.day_of_month || "",
          annual_month: r.proposal?.month || "",
          annual_day: r.proposal?.day_of_month || "",
          category: r.proposal?.category || "",
          reference_number: r.proposal?.reference_number || "",
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

      {monthlyCount > 1 && (
        <div className="rounded-2xl border border-ink-100 bg-ink-50 p-4">
          <label className="flex items-center gap-2 text-sm font-semibold text-ink-700">
            <input
              type="checkbox"
              checked={sameDayEnabled}
              onChange={(e) => setSameDayEnabled(e.target.checked)}
              className="h-4 w-4 rounded border-ink-300 text-brand-600 focus:ring-brand-400"
            />
            Set all monthly bills to the same day
          </label>
          {sameDayEnabled && (
            <div className="mt-2 flex items-center gap-2">
              <span className="text-sm text-ink-500">Day:</span>
              <input
                type="number"
                min="1"
                max="31"
                value={sameDayValue}
                onChange={(e) => setSameDayValue(e.target.value)}
                placeholder="e.g. 15"
                className="w-24 rounded-lg border border-ink-200 px-3 py-1.5 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
              />
              <span className="text-xs text-ink-400">Applies to the {monthlyCount} monthly bills below only.</span>
            </div>
          )}
        </div>
      )}

      {active.map((r) => (
        <div key={r.key} className="rounded-2xl border border-ink-100 bg-white p-4 shadow-sm">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            {r.proposal?.likely_duplicate && (
              <span className="rounded-full bg-warn-100 px-2.5 py-1 text-xs font-semibold text-warn-700">
                Possible duplicate in this upload — check before confirming
              </span>
            )}
            <button onClick={() => remove(r.key)} className="ml-auto flex items-center gap-1 text-xs font-semibold text-danger-600 hover:underline">
              <TrashIcon className="h-3.5 w-3.5" /> Remove
            </button>
          </div>

          {r.proposal?.existing_duplicate && (
            <div className="mb-3 flex flex-wrap items-center justify-between gap-2 rounded-xl bg-warn-50 p-3 text-sm text-warn-700">
              <span>
                This bill may already exist{r.proposal.existing_duplicate_bill_name ? ` (${r.proposal.existing_duplicate_bill_name})` : ""}.
              </span>
              <a
                href={`/bills/${r.proposal.existing_duplicate_bill_id}`}
                target="_blank"
                rel="noopener noreferrer"
                className="font-semibold underline"
              >
                View existing bill
              </a>
            </div>
          )}

          {!r.aiAvailable && (
            <p className="mb-3 rounded-xl bg-warn-50 p-3 text-sm text-warn-700">
              We couldn't read this automatically — please enter it manually.
            </p>
          )}
          {r.aiAvailable && !r.proposal && (
            <p className="mb-3 rounded-xl bg-warn-50 p-3 text-sm text-warn-700">
              {r.message || "We couldn't find a bill in this file — please enter it manually."}
            </p>
          )}

          <MiniBillEditor
            initial={{
              name: r.proposal?.name || "",
              amount: r.proposal?.amount || "",
              recurrence: r.proposal?.recurrence || "monthly",
              due_date: r.proposal?.due_date || "",
              day_of_month: r.proposal?.day_of_month || "",
              annual_month: r.proposal?.month || "",
              annual_day: r.proposal?.day_of_month || "",
              category: r.proposal?.category || "",
              reference_number: r.proposal?.reference_number || "",
            }}
            needsReview={r.proposal?.needs_review || []}
            onChange={(values) => setValues(r.key, values)}
            sameDayOverride={sameDayEnabled && sameDayValue && currentRecurrence(r) === "monthly" ? sameDayValue : null}
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

function MiniBillEditor({ initial, needsReview, onChange, sameDayOverride }) {
  const [values, setValues] = useState(initial);

  function update(field, value) {
    const next = { ...values, [field]: value };
    setValues(next);
    onChange(next);
  }

  // When "Set all monthly bills to the same day" is on, this bill's
  // day-of-month follows the shared value instead of its own -- but only
  // while the checkbox is active, and only ever for a bill whose recurrence
  // is (currently) monthly, so annual/weekly/quarterly bills are never
  // touched. Turning the checkbox off just leaves whatever value was last
  // applied, editable individually again.
  useEffect(() => {
    if (sameDayOverride !== null && sameDayOverride !== undefined && sameDayOverride !== values.day_of_month) {
      update("day_of_month", sameDayOverride);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [sameDayOverride]);

  const fieldClass = (field) =>
    `w-full rounded-lg border px-3 py-2 text-sm outline-none focus:ring-2 ${
      needsReview.includes(field) ? "border-warn-300 bg-warn-50 focus:border-warn-400 focus:ring-warn-100" : "border-ink-200 focus:border-brand-400 focus:ring-brand-100"
    }`;

  return (
    <div className="grid grid-cols-2 gap-2">
      <input className={`col-span-2 ${fieldClass("name")}`} placeholder="Bill name" value={values.name} onChange={(e) => update("name", e.target.value)} />
      <input className={fieldClass("amount")} placeholder="Amount" type="number" step="0.01" value={values.amount} onChange={(e) => update("amount", e.target.value)} />
      <select className={fieldClass("recurrence")} value={values.recurrence} onChange={(e) => update("recurrence", e.target.value)}>
        <option value="none">One-time</option>
        <option value="weekly">Weekly</option>
        <option value="monthly">Monthly</option>
        <option value="quarterly">Quarterly</option>
        <option value="yearly">Yearly</option>
      </select>

      {values.recurrence === "monthly" && (
        <input
          className={fieldClass("day_of_month")}
          placeholder="Day of month (1-31)"
          type="number"
          min="1"
          max="31"
          value={values.day_of_month}
          onChange={(e) => update("day_of_month", e.target.value)}
          disabled={sameDayOverride !== null && sameDayOverride !== undefined}
        />
      )}

      {values.recurrence === "yearly" && (
        <>
          <select className={fieldClass("month")} value={values.annual_month} onChange={(e) => update("annual_month", e.target.value)}>
            <option value="">Month</option>
            {MONTH_LABELS.map((label, idx) => (
              <option key={label} value={idx + 1}>
                {label}
              </option>
            ))}
          </select>
          <input
            className={fieldClass("day_of_month")}
            placeholder="Day"
            type="number"
            min="1"
            max="31"
            value={values.annual_day}
            onChange={(e) => update("annual_day", e.target.value)}
          />
        </>
      )}

      {(values.recurrence === "weekly" || values.recurrence === "quarterly" || values.recurrence === "none") && (
        <input className={fieldClass("due_date")} type="date" value={values.due_date} onChange={(e) => update("due_date", e.target.value)} />
      )}

      <input
        className={`col-span-2 ${fieldClass("reference_number")}`}
        placeholder="Invoice / account number (optional)"
        value={values.reference_number}
        onChange={(e) => update("reference_number", e.target.value)}
      />
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
          due_date: proposal.due_date || "",
          day_of_month: proposal.day_of_month || "",
          annual_month: proposal.month || "",
          annual_day: proposal.day_of_month || "",
          category: proposal.category || "",
          reference_number: proposal.reference_number || "",
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
