import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import BillCard from "../components/BillCard";
import CaughtUpBanner from "../components/CaughtUpBanner";
import { formatMoney } from "../utils/format";
import { AlertTriangleIcon, ChevronRightIcon } from "../components/icons";
import { useToast } from "../context/ToastContext";

export default function Dashboard() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const { show } = useToast();

  const load = useCallback(async () => {
    const result = await api.dashboard.get();
    setData(result);
  }, []);

  useEffect(() => {
    load().finally(() => setLoading(false));
  }, [load]);

  async function handleMarkPaid(occurrenceId) {
    const before = data;
    try {
      await api.occurrences.markPaid(occurrenceId);
      await load();
      show("Marked as paid.", { type: "success" });
    } catch (err) {
      setData(before);
      show(err.message || "Couldn't mark that as paid.", { type: "error" });
      throw err;
    }
  }

  if (loading || !data) {
    return (
      <div className="space-y-4">
        <div className="h-28 animate-pulse rounded-3xl bg-ink-100" />
        <div className="h-20 animate-pulse rounded-2xl bg-ink-100" />
        <div className="h-20 animate-pulse rounded-2xl bg-ink-100" />
      </div>
    );
  }

  return (
    <div className="space-y-8">
      {/* 1. Overall status */}
      {data.caught_up ? (
        <CaughtUpBanner nextUpcoming={data.next_upcoming} />
      ) : (
        <div className="animate-billio-fade-in rounded-3xl border border-danger-100 bg-danger-50 p-5">
          <div className="flex items-center gap-3">
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-danger-600 text-white">
              <AlertTriangleIcon className="h-6 w-6" />
            </div>
            <div>
              <p className="font-bold text-danger-700">
                {data.attention_count} bill{data.attention_count !== 1 ? "s" : ""} need{data.attention_count === 1 ? "s" : ""} your attention
              </p>
              <p className="text-sm text-danger-700/80">{formatMoney(data.outstanding_total)} outstanding</p>
            </div>
          </div>
        </div>
      )}

      {/* 2. Monthly recurring spend */}
      <div className="rounded-3xl border border-ink-100 bg-white p-5 shadow-sm">
        <p className="text-xs font-semibold uppercase tracking-wide text-ink-400">Monthly recurring</p>
        <p className="mt-1 text-3xl font-extrabold tabular-nums text-ink-900">{formatMoney(data.monthly_recurring_total)}</p>
      </div>

      {/* 3. Urgent bills */}
      {data.urgent.length > 0 && (
        <section>
          <h2 className="mb-3 text-sm font-bold uppercase tracking-wide text-danger-700">Needs attention</h2>
          <div className="space-y-3">
            {data.urgent.map((occ) => (
              <BillCard key={occ.id} occurrence={occ} onMarkPaid={handleMarkPaid} />
            ))}
          </div>
        </section>
      )}

      {/* 4. Coming up */}
      <section>
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-bold uppercase tracking-wide text-ink-500">Coming up</h2>
        </div>
        {data.upcoming.length === 0 ? (
          <p className="rounded-2xl border border-dashed border-ink-200 p-5 text-center text-sm text-ink-400">
            Nothing else coming up right now.
          </p>
        ) : (
          <div className="space-y-3">
            {data.upcoming.slice(0, 8).map((occ) => (
              <BillCard key={occ.id} occurrence={occ} onMarkPaid={handleMarkPaid} />
            ))}
          </div>
        )}
      </section>

      {/* 5. Paid */}
      {data.recently_paid.length > 0 && (
        <section>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="text-sm font-bold uppercase tracking-wide text-good-700">Paid</h2>
            <Link to="/history" className="flex items-center text-xs font-semibold text-brand-600 hover:underline">
              Full history <ChevronRightIcon />
            </Link>
          </div>
          <div className="space-y-3">
            {data.recently_paid.slice(0, 5).map((occ) => (
              <BillCard key={occ.id} occurrence={occ} onMarkPaid={handleMarkPaid} dense />
            ))}
          </div>
        </section>
      )}

      {data.urgent.length === 0 && data.upcoming.length === 0 && data.recently_paid.length === 0 && (
        <EmptyDashboard />
      )}
    </div>
  );
}

function EmptyDashboard() {
  return (
    <div className="rounded-3xl border border-dashed border-ink-200 bg-white p-8 text-center">
      <h3 className="text-lg font-bold text-ink-900">Let's add your first bill</h3>
      <p className="mx-auto mt-1 max-w-xs text-sm text-ink-500">
        Enter it manually or snap a photo — Billio will remember it and remind you when it's due.
      </p>
      <div className="mt-5 flex flex-col justify-center gap-2 sm:flex-row">
        <Link to="/bills/new?mode=manual" className="rounded-xl bg-ink-900 px-4 py-2.5 text-sm font-semibold text-white hover:bg-ink-800">
          Enter manually
        </Link>
        <Link to="/bills/new?mode=photo" className="rounded-xl border border-ink-200 px-4 py-2.5 text-sm font-semibold text-ink-700 hover:bg-ink-50">
          Upload a photo
        </Link>
      </div>
    </div>
  );
}
