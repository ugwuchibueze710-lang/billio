import logging

from flask import Blueprint, jsonify, request, current_app

from app.extensions import db, limiter
from app.errors import ValidationError
from app.models import BillDocument
from app.schemas import serialize_document
from app.services import audit_engine
from app.services.extraction import normalize_extraction, detect_duplicates, check_existing_duplicates
from app.services.groq_client import (
    extract_bills_from_images,
    parse_bill_from_text,
    explain_audit,
    parse_audit_intent,
    GroqUnavailableError,
)
from app.services.assistant import run_assistant
from app.services.image_validation import validate_bill_image, validate_bill_pdf, is_pdf
from app.services.recurrence import resolve_monthly_due_date
from app.services.status import user_today
from app.services.storage import build_storage_key, upload_bytes
from app.utils.security import get_current_user
from app.utils.validation import get_json_body, validate_date_field

logger = logging.getLogger("billio.ai")

bp = Blueprint("ai", __name__, url_prefix="/api/ai")


def _store_uploaded_file(user, file_storage):
    """
    Stores whatever the user uploaded (image or PDF) EXACTLY ONCE and
    returns (storage_key, file_type, file_size_bytes, original_filename,
    page_png_bytes_for_extraction). For a PDF, the *original* PDF is what
    gets stored (so the user can download their real file later) but
    rasterized page images (up to image_validation.MAX_PDF_PAGES_FOR_EXTRACTION)
    are what's handed to Groq, since Groq's vision endpoint only accepts
    images. All pages/images are treated as one document that may contain
    one or several distinct bills -- see groq_client.extract_bills_from_images.
    """
    if file_storage is None or file_storage.filename == "":
        raise ValidationError("No file was provided.")

    original_filename = (file_storage.filename or "")[:255] or None

    if is_pdf(file_storage):
        pdf_bytes, page_pngs = validate_bill_pdf(file_storage)
        storage_key = build_storage_key(user.id, "application/pdf")
        upload_bytes(storage_key, pdf_bytes, "application/pdf")
        return storage_key, "application/pdf", len(pdf_bytes), original_filename, page_pngs

    data, content_type = validate_bill_image(file_storage)
    storage_key = build_storage_key(user.id, content_type)
    upload_bytes(storage_key, data, content_type)
    return storage_key, content_type, len(data), original_filename, [data]


def _create_document_row(user, storage_key, file_type, file_size_bytes, original_filename) -> BillDocument:
    doc = BillDocument(
        user_id=user.id,
        storage_key=storage_key,
        file_type=file_type,
        file_size_bytes=file_size_bytes,
        original_filename=original_filename,
    )
    db.session.add(doc)
    db.session.commit()
    return doc


def _extract_and_store_bills(user, file_storage) -> list[dict]:
    """
    Stores the uploaded file exactly once, then runs it through Groq
    extraction, which may find zero, one, or SEVERAL distinct bills in it
    (e.g. a one-page "monthly expenses" summary listing Electric, Water,
    Internet, and Insurance as separate charges). Creates one BillDocument
    metadata row PER bill found -- all sharing the same storage_key, so
    every resulting bill still links back to the one real uploaded file --
    or a single placeholder row if extraction found nothing or failed, so
    the upload is never silently lost.

    Returns a list of dicts: {"document": <serialized>, "ai_available":
    bool, "message": str|None, "proposal": dict|None}. Never raises
    GroqUnavailableError itself -- a failure just means every entry comes
    back with ai_available False and proposal None (i.e. "enter it
    manually"), same as before this file supported multi-bill documents.
    """
    storage_key, file_type, file_size_bytes, original_filename, page_pngs = _store_uploaded_file(
        user, file_storage
    )
    # validate_bill_image / validate_bill_pdf both normalize extraction
    # pages to PNG regardless of the original upload's real content type.
    extraction_content_type = "image/png"

    try:
        raw_bills = extract_bills_from_images(page_pngs, extraction_content_type)
    except GroqUnavailableError:
        logger.warning("extraction_unavailable", extra={"extra_fields": {"user_id": str(user.id)}})
        doc = _create_document_row(user, storage_key, file_type, file_size_bytes, original_filename)
        return [
            {
                "document": serialize_document(doc),
                "ai_available": False,
                "message": "We couldn't read this automatically — please enter it manually.",
                "proposal": None,
            }
        ]

    if not raw_bills:
        doc = _create_document_row(user, storage_key, file_type, file_size_bytes, original_filename)
        return [
            {
                "document": serialize_document(doc),
                "ai_available": True,
                "message": "We couldn't find a bill in this file — please enter it manually.",
                "proposal": None,
            }
        ]

    entries = []
    for raw in raw_bills:
        doc = _create_document_row(user, storage_key, file_type, file_size_bytes, original_filename)
        proposal = normalize_extraction(raw)
        entries.append({"document": serialize_document(doc), "ai_available": True, "message": None, "proposal": proposal})
    return entries


@bp.post("/extract-bill")
@limiter.limit(lambda: current_app.config["AI_RATE_LIMIT"])
def extract_bill():
    """
    Single-file extraction. A file can still yield MULTIPLE bills (see
    _extract_and_store_bills) -- callers that only want one result (the
    `flask test-image` CLI tool) get the first entry at the top level for
    backward compatibility; `results` carries every bill actually found.
    """
    user = get_current_user()
    file_storage = request.files.get("image")
    entries = _extract_and_store_bills(user, file_storage)

    proposals_only = [e["proposal"] for e in entries if e["proposal"] is not None]
    if proposals_only:
        detect_duplicates(proposals_only)
        check_existing_duplicates(user, proposals_only)

    first = entries[0]
    return jsonify({**first, "results": entries}), 200


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
        entries = _extract_and_store_bills(user, file_storage)
        if any(not e["ai_available"] for e in entries):
            any_ai_failure = True
        results.extend(entries)

    proposals_only = [r["proposal"] for r in results if r["proposal"] is not None]
    if proposals_only:
        # Batch-internal duplicates (the same bill captured twice across
        # uploaded files) AND duplicates against the user's already-saved
        # bills -- both flags land on the same proposal dicts.
        detect_duplicates(proposals_only)
        check_existing_duplicates(user, proposals_only)

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
    today = user_today(user.timezone)
    try:
        return resolve_monthly_due_date(today, day).isoformat()
    except ValueError:
        return None


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
