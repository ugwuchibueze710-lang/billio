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


def _clean_reference_number(value) -> str | None:
    if not isinstance(value, str):
        return None
    stripped = value.strip()
    if not stripped or len(stripped) > 100:
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
    # groq_client's extraction schema calls this "invoice_number" (it also
    # covers account/customer numbers); the rest of the app calls the same
    # concept "reference_number" (see BillDefinition.reference_number), so
    # it's renamed right here at the normalization boundary.
    reference_number = _clean_reference_number(raw.get("invoice_number"))
    confidence_notes = raw.get("confidence_notes") if isinstance(raw.get("confidence_notes"), str) else None

    # The user should never have to think about a YEAR for a monthly or
    # yearly bill (see app/services/recurrence.resolve_monthly_due_date /
    # resolve_annual_due_date) -- so alongside the full extracted due_date
    # (still returned as-is, and still what weekly/quarterly/one-time bills
    # use directly), also surface just the day-of-month, and just the
    # month, so the review screen can show the simplified input for
    # monthly/yearly bills instead of a full date. Both are simply read off
    # whatever due_date was extracted; a bill's actual recurrence anchor is
    # still resolved from these the same way manual entry resolves them.
    day_of_month = None
    month = None
    if due_date is not None:
        parsed_due_date = datetime.strptime(due_date, "%Y-%m-%d").date()
        day_of_month = parsed_due_date.day
        month = parsed_due_date.month

    needs_review = [
        field
        for field, value in (
            ("name", name),
            ("amount", amount),
            ("recurrence", recurrence),
        )
        if value is None
    ]
    if recurrence == "monthly":
        if day_of_month is None:
            needs_review.append("day_of_month")
    elif recurrence == "yearly":
        if day_of_month is None:
            needs_review.append("day_of_month")
        if month is None:
            needs_review.append("month")
    else:
        # weekly / quarterly / one-time / unknown recurrence -- these keep
        # using the full due_date field, unchanged.
        if due_date is None:
            needs_review.append("due_date")

    return {
        "name": name,
        "amount": amount,
        "due_date": due_date,
        "day_of_month": day_of_month,
        "month": month,
        "recurrence": recurrence,
        "category": category,
        "reference_number": reference_number,
        "confidence_notes": confidence_notes,
        "needs_review": needs_review,
    }


def detect_duplicates(proposals: list[dict]) -> list[dict]:
    """
    Deterministic (non-AI) duplicate detection across a batch: flags
    proposals that share the same reference/invoice number, OR the same
    normalized name + amount with a due date within 3 days of each other --
    almost certainly the same bill captured twice (e.g. a multi-page photo
    of one statement, or the same page uploaded twice by mistake).
    """

    def key_parts(p):
        name = (p.get("name") or "").strip().lower()
        amount = p.get("amount")
        return name, amount

    seen: dict[tuple, list[int]] = {}
    by_reference: dict[str, list[int]] = {}
    for idx, p in enumerate(proposals):
        ref = (p.get("reference_number") or "").strip().lower()
        if ref:
            by_reference.setdefault(ref, []).append(idx)
        name, amount = key_parts(p)
        if not name or amount is None:
            continue
        seen.setdefault((name, amount), []).append(idx)

    duplicate_indices: set[int] = set()

    for ref, indices in by_reference.items():
        if len(indices) > 1:
            duplicate_indices.update(indices[1:])  # keep the first occurrence, flag the rest

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


def check_existing_duplicates(user, proposals: list[dict]) -> list[dict]:
    """
    Beyond detect_duplicates() above (which only compares proposals within
    ONE upload batch), this checks each proposal against the user's
    EXISTING active saved bills already in the database -- by reference/
    account number, or by matching name + amount with a due date within 3
    days of an existing occurrence. Adds "existing_duplicate" (bool) and,
    when true, "existing_duplicate_bill_id" / "existing_duplicate_bill_name"
    so the frontend can show "This bill may already exist" with a link to
    the real existing bill, rather than silently letting the user create an
    actual duplicate record.
    """
    from app.models import BillDefinition, BillStatus

    existing = BillDefinition.query.filter_by(user_id=user.id, status=BillStatus.ACTIVE).all()
    if not existing:
        for p in proposals:
            p["existing_duplicate"] = False
            p["existing_duplicate_bill_id"] = None
            p["existing_duplicate_bill_name"] = None
        return proposals

    def norm(s):
        return (s or "").strip().lower()

    for p in proposals:
        match = None
        p_ref = norm(p.get("reference_number"))
        p_name = norm(p.get("name"))
        p_amount = p.get("amount")
        p_due = p.get("due_date")
        p_due_date = datetime.strptime(p_due, "%Y-%m-%d").date() if p_due else None

        for bill in existing:
            if p_ref and norm(bill.reference_number) == p_ref:
                match = bill
                break

        if match is None and p_name and p_amount is not None:
            for bill in existing:
                if norm(bill.name) != p_name:
                    continue
                try:
                    same_amount = abs(Decimal(str(bill.default_amount)) - Decimal(str(p_amount))) < Decimal("0.01")
                except (InvalidOperation, ValueError, TypeError):
                    same_amount = False
                if not same_amount:
                    continue
                if p_due_date is None:
                    match = bill
                    break
                close_due_date = any(
                    occ.due_date is not None and abs((occ.due_date - p_due_date).days) <= 3
                    for occ in bill.occurrences
                )
                if close_due_date:
                    match = bill
                    break

        p["existing_duplicate"] = match is not None
        p["existing_duplicate_bill_id"] = str(match.id) if match is not None else None
        p["existing_duplicate_bill_name"] = match.name if match is not None else None

    return proposals
