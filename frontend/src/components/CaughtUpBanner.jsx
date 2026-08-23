import { Link } from "react-router-dom";
import { formatMoney } from "../utils/format";
import { CheckCircleIcon } from "./icons";

export default function CaughtUpBanner({ nextUpcoming }) {
  return (
    <div className="animate-billio-fade-in rounded-3xl border border-good-100 bg-good-50 p-6 text-center sm:p-8">
      <div className="mx-auto flex h-14 w-14 items-center justify-center rounded-full bg-good-500 text-white shadow-sm">
        <CheckCircleIcon className="h-8 w-8" />
      </div>
      <h2 className="mt-4 text-xl font-bold text-good-700">You're all caught up</h2>
      <p className="mt-1 text-sm text-good-700/80">Every bill has been taken care of.</p>

      {nextUpcoming && (
        <Link
          to={`/bills/${nextUpcoming.bill_definition_id}?occurrence=${nextUpcoming.id}`}
          className="mt-5 inline-flex items-center gap-3 rounded-2xl border border-good-100 bg-white px-5 py-3 text-left shadow-sm transition hover:shadow-md"
        >
          <div>
            <p className="text-xs font-medium uppercase tracking-wide text-ink-400">Next bill</p>
            <p className="font-semibold text-ink-900">{nextUpcoming.name}</p>
          </div>
          <div className="text-right">
            <p className="font-bold text-ink-900">{formatMoney(nextUpcoming.amount)}</p>
            <p className="text-xs text-ink-400">{nextUpcoming.status_label}</p>
          </div>
        </Link>
      )}
    </div>
  );
}
