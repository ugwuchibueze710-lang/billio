import { useState } from "react";
import { api, ApiError } from "../api/client";
import { useToast } from "../context/ToastContext";
import { CloseIcon } from "./icons";

const TYPES = [
  { value: "review", label: "Review" },
  { value: "bug", label: "Bug" },
  { value: "improvement", label: "Improvement" },
  { value: "feature_request", label: "Feature request" },
  { value: "other", label: "Other" },
];

export default function FeedbackBar() {
  const [open, setOpen] = useState(false);
  const [type, setType] = useState("review");
  const [message, setMessage] = useState("");
  const [rating, setRating] = useState(0);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const { show } = useToast();

  function reset() {
    setType("review");
    setMessage("");
    setRating(0);
    setError(null);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (submitting || !message.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.feedback.submit({ type, message: message.trim(), rating: rating || undefined });
      reset();
      setOpen(false);
      show("Thanks. Your feedback has been received.", { type: "success" });
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.status === 429 ? "You're submitting feedback too quickly. Please try again in a bit." : err.message);
      } else {
        setError("Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-20 right-4 z-40 rounded-full bg-ink-900 px-4 py-2.5 text-xs font-semibold text-white shadow-lg transition hover:bg-ink-800 sm:bottom-6"
      >
        Have an idea or found a problem?
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-end justify-center bg-ink-950/40 backdrop-blur-sm sm:items-center" onClick={() => setOpen(false)}>
          <form
            onClick={(e) => e.stopPropagation()}
            onSubmit={handleSubmit}
            className="animate-billio-fade-in w-full max-w-md rounded-t-3xl bg-white p-6 shadow-2xl sm:rounded-3xl"
          >
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-bold text-ink-900">Send feedback</h3>
              <button type="button" onClick={() => setOpen(false)} className="rounded-full p-1 text-ink-400 hover:bg-ink-50">
                <CloseIcon />
              </button>
            </div>

            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink-400">Feedback type</label>
            <div className="mb-4 flex flex-wrap gap-2">
              {TYPES.map((t) => (
                <button
                  type="button"
                  key={t.value}
                  onClick={() => setType(t.value)}
                  className={`rounded-full px-3 py-1.5 text-sm font-medium transition ${
                    type === t.value ? "bg-brand-600 text-white" : "bg-ink-50 text-ink-600 hover:bg-ink-100"
                  }`}
                >
                  {t.label}
                </button>
              ))}
            </div>

            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink-400">Message</label>
            <textarea
              value={message}
              onChange={(e) => setMessage(e.target.value)}
              maxLength={5000}
              rows={4}
              required
              placeholder="What's frustrating, confusing, missing, or working well?"
              className="mb-4 w-full rounded-xl border border-ink-200 p-3 text-sm text-ink-900 outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
            />

            <label className="mb-1 block text-xs font-semibold uppercase tracking-wide text-ink-400">Rating (optional)</label>
            <div className="mb-5 flex gap-1">
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  type="button"
                  key={n}
                  onClick={() => setRating(rating === n ? 0 : n)}
                  className={`h-9 w-9 rounded-lg text-lg font-bold transition ${
                    n <= rating ? "bg-warn-500 text-white" : "bg-ink-50 text-ink-300 hover:bg-ink-100"
                  }`}
                  aria-label={`${n} star`}
                >
                  ★
                </button>
              ))}
            </div>

            {error && <p className="mb-3 text-sm font-medium text-danger-600">{error}</p>}

            <button
              type="submit"
              disabled={submitting || !message.trim()}
              className="w-full rounded-xl bg-ink-900 py-3 text-sm font-semibold text-white transition hover:bg-ink-800 disabled:opacity-50"
            >
              {submitting ? "Sending…" : "Submit feedback"}
            </button>
          </form>
        </div>
      )}
    </>
  );
}
