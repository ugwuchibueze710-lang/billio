import { useState } from "react";
import { api, ApiError } from "../api/client";
import { formatMoney } from "../utils/format";
import { SendIcon, SparkleIcon } from "../components/icons";

export default function Assistant() {
  const [tab, setTab] = useState("ask");

  return (
    <div>
      <h1 className="mb-1 text-2xl font-bold text-ink-900">Assistant</h1>
      <p className="mb-6 text-sm text-ink-500">Ask about your bills, or run an audit to see what changed.</p>

      <div className="mb-6 flex gap-2 rounded-2xl bg-ink-100 p-1">
        {[
          { key: "ask", label: "Ask" },
          { key: "audit", label: "Audit spending" },
        ].map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 rounded-xl py-2.5 text-sm font-semibold transition ${
              tab === t.key ? "bg-white text-ink-900 shadow-sm" : "text-ink-500"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {tab === "ask" ? <AskPanel /> : <AuditPanel />}
    </div>
  );
}

function AskPanel() {
  const [history, setHistory] = useState([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [aiAvailable, setAiAvailable] = useState(true);

  const suggestions = ["What's due this week?", "What's overdue?", "How much do I owe right now?", "Show me my paid bills."];

  async function send(text) {
    const message = text ?? input;
    if (!message.trim() || loading) return;
    setInput("");
    const nextHistory = [...history, { role: "user", content: message }];
    setHistory(nextHistory);
    setLoading(true);
    try {
      const res = await api.ai.assistant(message, history);
      setAiAvailable(res.ai_available);
      setHistory([...nextHistory, { role: "assistant", content: res.reply }]);
    } catch (err) {
      setHistory([
        ...nextHistory,
        { role: "assistant", content: err instanceof ApiError ? err.message : "Something went wrong." },
      ]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex flex-col">
      {!aiAvailable && (
        <p className="mb-4 rounded-xl bg-warn-50 p-3 text-sm text-warn-700">
          The assistant is temporarily unavailable. You can still manage your bills normally.
        </p>
      )}

      <div className="mb-4 min-h-[200px] space-y-3 rounded-2xl border border-ink-100 bg-white p-4">
        {history.length === 0 ? (
          <div className="py-6 text-center">
            <SparkleIcon className="mx-auto mb-2 h-6 w-6 text-brand-400" />
            <p className="text-sm text-ink-400">Ask me anything about your bills.</p>
            <div className="mt-4 flex flex-wrap justify-center gap-2">
              {suggestions.map((s) => (
                <button key={s} onClick={() => send(s)} className="rounded-full bg-ink-50 px-3 py-1.5 text-xs font-medium text-ink-600 hover:bg-ink-100">
                  {s}
                </button>
              ))}
            </div>
          </div>
        ) : (
          history.map((m, i) => (
            <div key={i} className={`flex ${m.role === "user" ? "justify-end" : "justify-start"}`}>
              <div
                className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${
                  m.role === "user" ? "bg-brand-600 text-white" : "bg-ink-50 text-ink-800"
                }`}
              >
                {m.content}
              </div>
            </div>
          ))
        )}
        {loading && <div className="text-sm text-ink-400">Thinking…</div>}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
        className="flex gap-2"
      >
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask about your bills…"
          className="flex-1 rounded-xl border border-ink-200 px-3.5 py-2.5 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
        />
        <button type="submit" disabled={loading} className="rounded-xl bg-ink-900 px-4 text-white hover:bg-ink-800 disabled:opacity-50">
          <SendIcon className="h-4 w-4" />
        </button>
      </form>
    </div>
  );
}

function AuditPanel() {
  const [question, setQuestion] = useState("");
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const suggestions = [
    "Why did I spend more this month?",
    "Compare this month with last month",
    "Do a hard audit of this month",
  ];

  async function runAudit(text) {
    const q = text ?? question;
    if (!q.trim() || loading) return;
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await api.ai.audit({ question: q });
      setResult(res);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div>
      <form
        onSubmit={(e) => {
          e.preventDefault();
          runAudit();
        }}
        className="mb-4 rounded-2xl border border-ink-100 bg-white p-4"
      >
        <p className="mb-2 text-sm font-semibold text-ink-700">What's happening with your money?</p>
        <textarea
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          rows={2}
          maxLength={1000}
          placeholder="e.g. We had $400 less left over this month than last month. Why?"
          className="w-full rounded-xl border border-ink-200 p-3 text-sm outline-none focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
        />
        <div className="mt-2 flex flex-wrap gap-2">
          {suggestions.map((s) => (
            <button
              type="button"
              key={s}
              onClick={() => {
                setQuestion(s);
                runAudit(s);
              }}
              className="rounded-full bg-ink-50 px-3 py-1.5 text-xs font-medium text-ink-600 hover:bg-ink-100"
            >
              {s}
            </button>
          ))}
        </div>
        <button
          type="submit"
          disabled={loading || !question.trim()}
          className="mt-3 w-full rounded-xl bg-ink-900 py-2.5 text-sm font-semibold text-white hover:bg-ink-800 disabled:opacity-50"
        >
          {loading ? "Auditing…" : "Run audit"}
        </button>
      </form>

      {error && <p className="text-sm font-medium text-danger-600">{error}</p>}
      {result && <AuditResult result={result} />}
    </div>
  );
}

function AuditResult({ result }) {
  const data = result.data;
  const comparison = data.comparison;

  return (
    <div className="space-y-4">
      {!result.ai_available && (
        <p className="rounded-xl bg-warn-50 p-3 text-sm text-warn-700">
          AI explanation is temporarily unavailable, but here are the calculated results.
        </p>
      )}

      <div className="rounded-2xl border border-brand-100 bg-brand-50 p-4">
        <p className="text-sm text-ink-800">{result.explanation.summary}</p>
        {result.explanation.narrative_points?.length > 0 && (
          <ul className="mt-2 list-inside list-disc space-y-1 text-sm text-ink-700">
            {result.explanation.narrative_points.map((p, i) => (
              <li key={i}>{p}</li>
            ))}
          </ul>
        )}
      </div>

      <div className="grid grid-cols-2 gap-3">
        <Stat label="This period" value={formatMoney(data.current_period.total)} />
        {comparison && <Stat label="Comparison period" value={formatMoney(comparison.previous_total)} />}
        {comparison && (
          <Stat
            label="Difference"
            value={`${Number(comparison.difference) >= 0 ? "+" : ""}${formatMoney(comparison.difference)}`}
            tone={Number(comparison.difference) > 0 ? "danger" : Number(comparison.difference) < 0 ? "good" : "neutral"}
          />
        )}
        <Stat label="Payments" value={data.current_period.payment_count} />
      </div>

      {comparison?.largest_increases?.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-500">Largest increases</h3>
          <div className="space-y-2">
            {comparison.largest_increases.map((row) => (
              <DriverRow key={row.name} row={row} />
            ))}
          </div>
        </div>
      )}

      {comparison?.largest_decreases?.length > 0 && (
        <div>
          <h3 className="mb-2 text-sm font-bold uppercase tracking-wide text-ink-500">Largest decreases</h3>
          <div className="space-y-2">
            {comparison.largest_decreases.map((row) => (
              <DriverRow key={row.name} row={row} />
            ))}
          </div>
        </div>
      )}

      {data.insufficient_data?.length > 0 && (
        <p className="rounded-xl bg-ink-50 p-3 text-xs text-ink-500">{data.insufficient_data.join(" ")}</p>
      )}
    </div>
  );
}

function Stat({ label, value, tone = "neutral" }) {
  const toneClass = tone === "danger" ? "text-danger-600" : tone === "good" ? "text-good-600" : "text-ink-900";
  return (
    <div className="rounded-2xl border border-ink-100 bg-white p-3.5">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-ink-400">{label}</p>
      <p className={`mt-0.5 text-lg font-bold tabular-nums ${toneClass}`}>{value}</p>
    </div>
  );
}

function DriverRow({ row }) {
  const diff = Number(row.difference);
  return (
    <div className="flex items-center justify-between rounded-xl border border-ink-100 bg-white px-3.5 py-2.5">
      <span className="text-sm font-medium text-ink-800">{row.name}</span>
      <span className={`text-sm font-bold tabular-nums ${diff > 0 ? "text-danger-600" : "text-good-600"}`}>
        {diff > 0 ? "+" : ""}
        {formatMoney(row.difference)}
      </span>
    </div>
  );
}
