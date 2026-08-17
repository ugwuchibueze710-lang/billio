import logging

from flask import Blueprint, jsonify, request, current_app

from app.extensions import db, limiter
from app.errors import ValidationError
from app.models import BillDocument
from app.schemas import serialize_document
from app.services import audit_engine
from app.services.extraction import normalize_extraction, detect_duplicates
from app.services.groq_client import (
    extract_bill_from_image,
    parse_bill_from_text,
    explain_audit,
    parse_audit_intent,
    GroqUnavailableError,
)
from app.services.assistant import run_assistant
from app.services.image_validation import validate_bill_image
from app.services.status import user_today
from app.services.storage import build_storage_key, upload_bytes
from app.utils.security import get_current_user
from app.utils.validation import get_json_body, validate_date_field

logger = logging.getLogger("billio.ai")

bp = Blueprint("ai", __name__, url_prefix="/api/ai")


def _store_uploaded_image(user, file_storage):
    data, content_type = validate_bill_image(file_storage)
    storage_key = build_storage_key(user.id, content_type)
    upload_bytes(storage_key, data, content_type)
    doc = BillDocument(
        user_id=user.id,
        storage_key=storage_key,
        file_type=content_type,
        file_size_bytes=len(data),
        original_filename=(file_storage.filename or "")[:255] or None,
    )
    db.session.add(doc)
    db.session.commit()
    return doc, data, content_type


@bp.post("/extract-bill")
@limiter.limit(lambda: current_app.config["AI_RATE_LIMIT"])
def extract_bill():
    user = get_current_user()
    file_storage = request.files.get("image")
    doc, data, content_type = _store_uploaded_image(user, file_storage)

    try:
        raw = extract_bill_from_image(data, content_type)
        proposal = normalize_extraction(raw)
        return jsonify({"document": serialize_document(doc), "ai_available": True, "proposal": proposal}), 200
    except GroqUnavailableError:
        logger.warning("extraction_unavailable", extra={"extra_fields": {"user_id": str(user.id)}})
        return (
            jsonify(
                {
                    "document": serialize_document(doc),
                    "ai_available": False,
                    "message": "We couldn't read this automatically — please enter it manually.",
                    "proposal": None,
                }
            ),
            200,
        )


@bp.post("/extract-bills-batch")
@limiter.limit(lambda: current_app.config["AI_RATE_LIMIT"])
def extract_bills_batch():
    user = get_current_user()
    files = request.files.getlist("images")
    if not files:
        raise ValidationError("At least one image is required.")
    max_images = current_app.config["MAX_BATCH_UPLOAD_IMAGES"]
    if len(files) > max_images:
        raise ValidationError(f"You can upload at most {max_images} images at once.")

    results = []
    any_ai_failure = False
    for file_storage in files:
        doc, data, content_type = _store_uploaded_image(user, file_storage)
        try:
            raw = extract_bill_from_image(data, content_type)
            proposal = normalize_extraction(raw)
            results.append({"document": serialize_document(doc), "ai_available": True, "proposal": proposal})
        except GroqUnavailableError:
            any_ai_failure = True
            results.append(
                {
                    "document": serialize_document(doc),
                    "ai_available": False,
                    "message": "We couldn't read this one automatically — please enter it manually.",
                    "proposal": None,
                }
            )

    proposals_only = [r["proposal"] for r in results if r["proposal"] is not None]
    flagged = detect_duplicates(proposals_only)
    flag_iter = iter(flagged)
    for r in results:
        if r["proposal"] is not None:
            r["proposal"] = next(flag_iter)

    return jsonify({"results": results, "any_ai_failure": any_ai_failure}), 200


@bp.post("/parse-text")
@limiter.limit(lambda: current_app.config["AI_RATE_LIMIT"])
def parse_text():
    user = get_current_user()
    body = get_json_body()
    description = body.get("description")
    if not isinstance(description, str) or not description.strip():
        raise ValidationError("description is required.")
    if len(description) > 500:
        raise ValidationError("description is too long.")

    try:
        raw = parse_bill_from_text(description)
    except GroqUnavailableError:
        return (
            jsonify(
                {
                    "ai_available": False,
                    "message": "Natural-language entry is temporarily unavailable — please use the form instead.",
                    "proposal": None,
                }
            ),
            200,
        )

    # parse-text returns due_day (day-of-month) rather than a full date in
    # some cases; resolve it to a concrete upcoming date server-side.
    due_date = raw.get("due_date")
    if not due_date and raw.get("due_day"):
        due_date = _resolve_due_day(user, raw.get("due_day"))
        raw["due_date"] = due_date

    proposal = normalize_extraction(raw)
    return jsonify({"ai_available": True, "proposal": proposal}), 200


def _resolve_due_day(user, due_day) -> str | None:
    try:
        day = int(due_day)
    except (ValueError, TypeError):
        return None
    if not (1 <= day <= 31):
        return None
    from calendar import monthrange
    from datetime import date

    today = user_today(user.timezone)
    year, month = today.year, today.month
    clamped_day = min(day, monthrange(year, month)[1])
    candidate = date(year, month, clamped_day)
    if candidate < today:
        month += 1
        if month > 12:
            month = 1
            year += 1
        clamped_day = min(day, monthrange(year, month)[1])
        candidate = date(year, month, clamped_day)
    return candidate.isoformat()


@bp.post("/assistant")
@limiter.limit(lambda: current_app.config["AI_RATE_LIMIT"])
def assistant():
    user = get_current_user()
    body = get_json_body()
    message = body.get("message")
    history = body.get("history") if isinstance(body.get("history"), list) else []
    # Only allow role/content shaped history entries through -- discard
    # anything else a malicious client might inject.
    safe_history = [
        {"role": m.get("role"), "content": m.get("content")}
        for m in history[-10:]
        if isinstance(m, dict) and m.get("role") in ("user", "assistant") and isinstance(m.get("content"), str)
    ]

    try:
        result = run_assistant(user, message, safe_history)
        return jsonify({"ai_available": True, **result}), 200
    except GroqUnavailableError:
        return (
            jsonify(
                {
                    "ai_available": False,
                    "reply": "The assistant is temporarily unavailable. You can still manage your bills normally.",
                    "actions": [],
                }
            ),
            200,
        )


@bp.post("/audit")
@limiter.limit(lambda: current_app.config["AI_RATE_LIMIT"])
def audit():
    user = get_current_user()
    body = get_json_body()
    question = body.get("question")
    if not isinstance(question, str) or not question.strip():
        raise ValidationError("question is required.")
    if len(question) > 1000:
        raise ValidationError("question is too long.")

    today = user_today(user.timezone)

    period = body.get("period")
    comparison = body.get("comparison")
    hard_audit = bool(body.get("hard_audit", False))
    custom_start = validate_date_field(body.get("custom_start"), "custom_start") if body.get("custom_start") else None
    custom_end = validate_date_field(body.get("custom_end"), "custom_end") if body.get("custom_end") else None

    intent_source = "explicit"
    if period is None and comparison is None and not body.get("hard_audit_set"):
        try:
            intent = parse_audit_intent(question, today.isoformat())
            period = intent.get("period", "this_month")
            comparison = intent.get("comparison", "previous_month")
            hard_audit = bool(intent.get("hard_audit", False))
            if intent.get("custom_start"):
                custom_start = validate_date_field(intent["custom_start"], "custom_start")
            if intent.get("custom_end"):
                custom_end = validate_date_field(intent["custom_end"], "custom_end")
            intent_source = "ai"
        except GroqUnavailableError:
            period = period or "this_month"
            comparison = comparison or "previous_month"
            intent_source = "default_fallback"

    start, end = _resolve_period(today, period, custom_start, custom_end)
    comparison_start, comparison_end = _resolve_comparison(start, end, comparison)

    dataset = audit_engine.run_audit(
        user,
        start=start,
        end=end,
        comparison_start=comparison_start,
        comparison_end=comparison_end,
        hard_audit=hard_audit,
    )

    explanation = None
    ai_available = True
    try:
        known_numbers = audit_engine.collect_known_numbers(dataset)
        ai_result = explain_audit(question, dataset)
        summary = ai_result.get("summary", "")
        points = ai_result.get("narrative_points", [])
        full_text = summary + " " + " ".join(p for p in points if isinstance(p, str))
        if audit_engine.validate_narrative_numbers(full_text, known_numbers):
            explanation = {"summary": summary, "narrative_points": points, "source": "ai"}
        else:
            logger.warning("audit_ai_hallucination_detected", extra={"extra_fields": {"user_id": str(user.id)}})
            explanation = None
    except GroqUnavailableError:
        ai_available = False

    if explanation is None:
        explanation = {
            "summary": audit_engine.deterministic_summary_sentence(dataset),
            "narrative_points": [],
            "source": "deterministic",
        }

    return (
        jsonify(
            {
                "question": question,
                "intent_source": intent_source,
                "ai_available": ai_available,
                "explanation": explanation,
                "data": _serialize_dataset(dataset),
            }
        ),
        200,
    )


def _resolve_period(today, period, custom_start, custom_end):
    if period == "last_month":
        return audit_engine.previous_month_bounds(today)
    if period == "custom":
        if not custom_start or not custom_end:
            raise ValidationError("custom_start and custom_end are required for a custom period.")
        if custom_start > custom_end:
            raise ValidationError("custom_start must be before custom_end.")
        return custom_start, custom_end
    return audit_engine.month_bounds(today)  # default: this_month


def _resolve_comparison(start, end, comparison):
    if comparison == "previous_month":
        return audit_engine.previous_month_bounds(start)
    if comparison == "previous_period":
        return audit_engine.previous_period_bounds(start, end)
    if comparison == "same_month_last_year":
        return audit_engine.same_month_last_year_bounds(start)
    return None, None


def _serialize_dataset(dataset: dict) -> dict:
    import json

    return json.loads(json.dumps(dataset, default=str))
