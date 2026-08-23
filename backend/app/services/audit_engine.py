"""
Deterministic financial audit engine. EVERY number in this module is
computed with Python's Decimal from real Payment/BillOccurrence rows --
Groq never touches this arithmetic (see app/services/groq_client.py's
module docstring). This module produces a plain-JSON-serializable dataset;
app/api/ai.py optionally sends that dataset (and only that dataset) to
Groq for a natural-language explanation, then validates the explanation
doesn't introduce unsupported figures before returning it.
"""
from collections import defaultdict
from calendar import monthrange
from datetime import date, timedelta
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from app.extensions import db
from app.models import Payment, BillOccurrence

ZERO = Decimal("0.00")


def _q(value) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def month_bounds(d: date) -> tuple[date, date]:
    return date(d.year, d.month, 1), date(d.year, d.month, monthrange(d.year, d.month)[1])


def previous_month_bounds(d: date) -> tuple[date, date]:
    first_of_this_month = date(d.year, d.month, 1)
    last_month_end = first_of_this_month - timedelta(days=1)
    return month_bounds(last_month_end)


def same_month_last_year_bounds(d: date) -> tuple[date, date]:
    shifted = d - relativedelta(years=1)
    return month_bounds(shifted)


def previous_period_bounds(start: date, end: date) -> tuple[date, date]:
    span_days = (end - start).days + 1
    prev_end = start - timedelta(days=1)
    prev_start = prev_end - timedelta(days=span_days - 1)
    return prev_start, prev_end


def earliest_history_date(user) -> date | None:
    earliest = (
        db.session.query(db.func.min(BillOccurrence.due_date)).filter(BillOccurrence.user_id == user.id).scalar()
    )
    return earliest


def data_sufficiency_days(user) -> int:
    earliest = earliest_history_date(user)
    if earliest is None:
        return 0
    return (date.today() - earliest).days


def _payments_in_range(user, start: date, end: date) -> list[Payment]:
    return (
        Payment.query.filter(
            Payment.user_id == user.id,
            Payment.paid_at >= _start_of_day_utc(start),
            Payment.paid_at < _start_of_day_utc(end + timedelta(days=1)),
        )
        .order_by(Payment.paid_at.asc())
        .all()
    )


def _start_of_day_utc(d: date):
    from datetime import datetime, timezone

    return datetime(d.year, d.month, d.day, tzinfo=timezone.utc)


def period_totals(user, start: date, end: date) -> dict:
    payments = _payments_in_range(user, start, end)

    total = sum((p.amount_paid for p in payments), ZERO)

    by_category: dict[str, Decimal] = defaultdict(lambda: ZERO)
    by_bill: dict[str, Decimal] = defaultdict(lambda: ZERO)
    by_date: dict[str, Decimal] = defaultdict(lambda: ZERO)
    bill_payment_dates: dict[str, list[str]] = defaultdict(list)

    for p in payments:
        category = p.category or "uncategorized"
        by_category[category] += p.amount_paid
        by_bill[p.bill_name] += p.amount_paid
        paid_date_str = p.paid_at.date().isoformat()
        by_date[paid_date_str] += p.amount_paid
        bill_payment_dates[p.bill_name].append(paid_date_str)

    return {
        "start": start.isoformat(),
        "end": end.isoformat(),
        "total": _q(total),
        "payment_count": len(payments),
        "by_category": {k: _q(v) for k, v in by_category.items()},
        "by_bill": {k: _q(v) for k, v in by_bill.items()},
        "by_date": {k: _q(v) for k, v in by_date.items()},
        "bill_payment_dates": dict(bill_payment_dates),
    }


def weekly_breakdown(start: date, end: date, by_date: dict[str, str]) -> list[dict]:
    """Buckets a period's daily totals into ~7-day chunks."""
    buckets = []
    cursor = start
    while cursor <= end:
        bucket_end = min(cursor + timedelta(days=6), end)
        total = ZERO
        d = cursor
        while d <= bucket_end:
            total += Decimal(by_date.get(d.isoformat(), "0"))
            d += timedelta(days=1)
        buckets.append({"start": cursor.isoformat(), "end": bucket_end.isoformat(), "total": _q(total)})
        cursor = bucket_end + timedelta(days=1)
    return buckets


def multiple_payments_close_together(bill_payment_dates: dict[str, list[str]], threshold_days: int = 5) -> list[dict]:
    flagged = []
    for bill_name, dates in bill_payment_dates.items():
        if len(dates) < 2:
            continue
        parsed = sorted(date.fromisoformat(d) for d in dates)
        for i in range(len(parsed) - 1):
            if (parsed[i + 1] - parsed[i]).days <= threshold_days:
                flagged.append(
                    {
                        "bill_name": bill_name,
                        "dates": [d.isoformat() for d in parsed],
                        "message": f"Billio found {len(parsed)} payments for {bill_name} within the selected period.",
                    }
                )
                break
    return flagged


def compare(current: dict, previous: dict) -> dict:
    current_total = Decimal(str(current["total"]))
    previous_total = Decimal(str(previous["total"]))
    difference = _q(current_total - previous_total)
    percent_change = None
    if previous_total != 0:
        percent_change = float((difference / previous_total * 100).quantize(Decimal("0.1")))

    def diff_rows(current_map: dict, previous_map: dict) -> list[dict]:
        keys = set(current_map) | set(previous_map)
        rows = []
        for key in keys:
            cur = Decimal(str(current_map.get(key, "0")))
            prev = Decimal(str(previous_map.get(key, "0")))
            diff = _q(cur - prev)
            pct = None
            if prev != 0:
                pct = float((diff / prev * 100).quantize(Decimal("0.1")))
            rows.append(
                {
                    "name": key,
                    "current": _q(cur),
                    "previous": _q(prev),
                    "difference": diff,
                    "percent_change": pct,
                }
            )
        rows.sort(key=lambda r: abs(r["difference"]), reverse=True)
        return rows

    bill_diffs = diff_rows(current["by_bill"], previous["by_bill"])
    category_diffs = diff_rows(current["by_category"], previous["by_category"])

    newly_appearing = [row["name"] for row in bill_diffs if row["previous"] == ZERO and row["current"] > ZERO]
    disappeared = [row["name"] for row in bill_diffs if row["current"] == ZERO and row["previous"] > ZERO]
    changed_amounts = [
        row for row in bill_diffs if row["previous"] > ZERO and row["current"] > ZERO and row["difference"] != ZERO
    ]

    return {
        "current_total": _q(current_total),
        "previous_total": _q(previous_total),
        "difference": difference,
        "percent_change": percent_change,
        "bill_differences": bill_diffs[:25],
        "category_differences": category_diffs[:25],
        "largest_increases": [r for r in bill_diffs if r["difference"] > ZERO][:10],
        "largest_decreases": [r for r in bill_diffs if r["difference"] < ZERO][:10],
        "newly_appearing_bills": newly_appearing,
        "disappeared_bills": disappeared,
        "changed_amount_bills": changed_amounts,
    }


def run_audit(user, *, start: date, end: date, comparison_start: date | None, comparison_end: date | None, hard_audit: bool) -> dict:
    """Produces the full structured audit dataset. Never touches Groq."""
    current = period_totals(user, start, end)
    result = {
        "current_period": current,
        "history_days_available": data_sufficiency_days(user),
        "insufficient_data": [],
    }

    if data_sufficiency_days(user) < 14:
        result["insufficient_data"].append(
            f"Billio only has {data_sufficiency_days(user)} day(s) of bill history, "
            f"so comparisons may not be meaningful yet."
        )

    if comparison_start is not None and comparison_end is not None:
        previous = period_totals(user, comparison_start, comparison_end)
        result["comparison_period"] = previous
        result["comparison"] = compare(current, previous)

    if hard_audit:
        result["weekly_breakdown"] = weekly_breakdown(start, end, current["by_date"])
        result["multiple_payments_close_together"] = multiple_payments_close_together(current["bill_payment_dates"])
        midpoint = start + (end - start) // 2
        first_half = sum(
            (Decimal(v) for k, v in current["by_date"].items() if date.fromisoformat(k) <= midpoint), ZERO
        )
        second_half = sum(
            (Decimal(v) for k, v in current["by_date"].items() if date.fromisoformat(k) > midpoint), ZERO
        )
        result["first_half_total"] = _q(first_half)
        result["second_half_total"] = _q(second_half)

    return result


def deterministic_summary_sentence(dataset: dict) -> str:
    """A plain, non-AI fallback summary used when Groq is unavailable or
    its explanation fails validation."""
    current = dataset["current_period"]
    parts = [f"You paid ${current['total']} across {current['payment_count']} bill(s) from {current['start']} to {current['end']}."]

    comparison = dataset.get("comparison")
    if comparison:
        diff = Decimal(str(comparison["difference"]))
        if diff > ZERO:
            parts.append(f"That is ${abs(diff)} more than the comparison period (${comparison['previous_total']}).")
        elif diff < ZERO:
            parts.append(f"That is ${abs(diff)} less than the comparison period (${comparison['previous_total']}).")
        else:
            parts.append("That matches the comparison period exactly.")

        top = comparison["largest_increases"][:2]
        if top:
            drivers = ", ".join(f"{r['name']} (+${r['difference']})" for r in top)
            parts.append(f"The largest increases were: {drivers}.")

    for note in dataset.get("insufficient_data", []):
        parts.append(note)

    return " ".join(parts)


def validate_narrative_numbers(text: str, known_numbers: set[str], tolerance: Decimal = Decimal("0.02")) -> bool:
    """
    Returns False if `text` contains a dollar-amount-looking number that
    doesn't correspond (within a small tolerance) to anything in
    known_numbers -- i.e. Groq appears to have invented a figure. Percent
    signs and prose numbers unrelated to money (e.g. "2 bills") are allowed
    through since we only police claims that look like currency, which is
    where hallucinated financial figures would actually cause harm.
    """
    import re

    known_floats = set()
    for n in known_numbers:
        try:
            known_floats.add(round(float(n), 2))
        except ValueError:
            continue

    for match in re.finditer(r"\$\s?-?\d[\d,]*(?:\.\d+)?", text):
        raw = match.group().replace("$", "").replace(",", "").strip()
        try:
            value = round(float(raw), 2)
        except ValueError:
            continue
        if not any(abs(value - k) <= float(tolerance) for k in known_floats):
            return False
    return True


def collect_known_numbers(dataset: dict) -> set[str]:
    """Every dollar figure and percentage present in the dataset, used to
    validate that Groq's narrative doesn't cite a number we didn't compute."""
    numbers: set[str] = set()

    def walk(value):
        if isinstance(value, dict):
            for v in value.values():
                walk(v)
        elif isinstance(value, list):
            for v in value:
                walk(v)
        elif isinstance(value, (int, float, Decimal)):
            numbers.add(str(value))
            try:
                numbers.add(f"{float(value):.2f}")
                numbers.add(f"{float(value):.1f}")
                numbers.add(str(int(round(float(value)))))
            except (ValueError, TypeError):
                pass

    walk(dataset)
    return numbers
