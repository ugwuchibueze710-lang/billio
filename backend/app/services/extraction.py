"""
Validates and normalizes raw Groq extraction output before it is ever shown
to the user or written anywhere. Nothing from this module is written to the
database directly -- it only produces a "proposal" the user must confirm
(and can edit) via the normal POST /api/bills endpoint, which re-validates
everything from scratch anyway.
"""
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from app.models.enums import SUGGESTED_CATEGORIES

_VALID_RECURRENCES = {"none", "weekly", "monthly", "quarterly", "yearly"}
_MIN_REASONABLE_DATE_PAST_DAYS = 30  # allow a little slack for already-overdue bills
_MAX_REASONABLE_DATE_FUTURE_DAYS = 400  # a bit over a year out


def _clean_amount(value) -> str | None:
    if value is None:
        return None
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if amount.is_nan() or amount.is_infinite() or amount <= 0:
        return None
    if amount > Decimal("1000000"):
        return None
    return str(amount.quantize(Decimal("0.01")))


def _clean_date(value) -> str | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        return None
    today = date.today()
    if parsed < today - timedelta(days=_MIN_REASONABLE_DATE_PAST_DAYS):
        return None
    if parsed > today + timedelta(days=_MAX_REASONABLE_DATE_FUTURE_DAYS):
        return None
    return parsed.isoformat()


def _clean_recurrence(value) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized if normalized in _VALID_RECURRENCES else None


def _clean_category(value) -> str | None:
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower()
    return normalized if normalized in SUGGESTED_CATEGORIES else None


def _clean_name(value) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or len(stripped) > 200:
        return None
    return stripped


def normalize_extraction(raw: dict) -> dict:
    """
    Turns raw (untrusted) Groq JSON into a safe proposal dict. Any field
    that fails validation becomes null and is added to `needs_review` so
    the frontend can prompt the user for it explicitly, rather than
    silently guessing or defaulting.
    """
    name = _clean_name(raw.get("name"))
    amount = _clean_amount(raw.get("amount"))
    due_date = _clean_date(raw.get("due_date"))
    recurrence = _clean_recurrence(raw.get("recurrence"))
    category = _clean_category(raw.get("category"))
    confidence_notes = raw.get("confidence_notes") if isinstance(raw.get("confidence_notes"), str) else None

    needs_review = [
        field
        for field, value in (
            ("name", name),
            ("amount", amount),
            ("due_date", due_date),
            ("recurrence", recurrence),
        )
        if value is None
    ]

    return {
        "name": name,
        "amount": amount,
        "due_date": due_date,
        "recurrence": recurrence,
        "category": category,
        "confidence_notes": confidence_notes,
        "needs_review": needs_review,
    }


def detect_duplicates(proposals: list[dict]) -> list[dict]:
    """
    Deterministic (non-AI) duplicate detection across a batch: flags
    proposals that share the same normalized name, amount, and a due date
    within 3 days of each other -- almost certainly the same bill captured
    twice (e.g. a multi-page photo of one statement).
    """

    def key_parts(p):
        name = (p.get("name") or "").strip().lower()
        amount = p.get("amount")
        return name, amount

    seen: dict[tuple, list[int]] = {}
    for idx, p in enumerate(proposals):
        name, amount = key_parts(p)
        if not name or amount is None:
            continue
        seen.setdefault((name, amount), []).append(idx)

    duplicate_indices: set[int] = set()
    for (name, amount), indices in seen.items():
        if len(indices) < 2:
            continue
        dates = []
        for idx in indices:
            due = proposals[idx].get("due_date")
            dates.append((idx, datetime.strptime(due, "%Y-%m-%d").date() if due else None))
        for i in range(len(dates)):
            for j in range(i + 1, len(dates)):
                idx_a, date_a = dates[i]
                idx_b, date_b = dates[j]
                if date_a is None or date_b is None or abs((date_a - date_b).days) <= 3:
                    duplicate_indices.add(idx_b)  # keep the first occurrence, flag the rest

    for idx, p in enumerate(proposals):
        p["likely_duplicate"] = idx in duplicate_indices

    return proposals
