"""
The AI assistant's function-calling loop. Groq only ever decides WHICH of
these functions to call and with what arguments -- every function below
independently re-scopes all data access to the authenticated `user` passed
in by the route handler (never a value the model could supply), performs
real database queries/calculations, and returns plain JSON. Groq never
touches SQL, never receives another user's data, and never performs the
underlying math itself.
"""
import logging
from decimal import Decimal

from app.errors import ValidationError
from app.models import BillDefinition, BillStatus
from app.services import bill_service, dashboard_service, history_service
from app.services.groq_client import run_assistant_turn, GroqUnavailableError
from app.services.status import user_today

logger = logging.getLogger("billio.assistant")

MAX_TOOL_ITERATIONS = 4


def _occurrence_brief(occ, bill) -> dict:
    return {
        "occurrence_id": str(occ.id),
        "bill_name": bill.name,
        "category": bill.category,
        "amount": str(occ.amount),
        "due_date": occ.due_date.isoformat(),
        "is_paid": occ.is_paid,
    }


def _fn_get_upcoming_bills(user, days: int = 30) -> dict:
    days = max(1, min(int(days or 30), 365))
    today = user_today(user.timezone)
    from datetime import timedelta

    query = bill_service.query_occurrences(user, status="upcoming", date_to=today + timedelta(days=days))
    results = query.limit(50).all()
    return {"bills": [_occurrence_brief(occ, bill) for occ, bill in results]}


def _fn_get_overdue_bills(user) -> dict:
    results = bill_service.query_occurrences(user, status="overdue").limit(50).all()
    return {"bills": [_occurrence_brief(occ, bill) for occ, bill in results]}


def _fn_get_due_today_bills(user) -> dict:
    results = bill_service.query_occurrences(user, status="due_today").limit(50).all()
    return {"bills": [_occurrence_brief(occ, bill) for occ, bill in results]}


def _fn_get_paid_bills(user, month: str | None = None) -> dict:
    date_from = date_to = None
    if month:
        date_from, date_to = history_service.parse_month(month)
    results = bill_service.query_occurrences(user, status="paid", date_from=date_from, date_to=date_to).limit(50).all()
    return {"bills": [_occurrence_brief(occ, bill) for occ, bill in results]}


def _fn_find_bill(user, name: str) -> dict:
    if not name:
        return {"matches": []}
    normalized = name.strip().lower()
    bills = (
        BillDefinition.query.filter(
            BillDefinition.user_id == user.id,
            BillDefinition.status == BillStatus.ACTIVE,
            BillDefinition.name.ilike(f"%{normalized}%"),
        )
        .limit(10)
        .all()
    )
    return {"matches": [{"bill_id": str(b.id), "name": b.name, "amount": str(b.default_amount)} for b in bills]}


def _fn_mark_bill_paid(user, name: str) -> dict:
    normalized = (name or "").strip().lower()
    if not normalized:
        return {"error": "no_name_provided"}

    bills = BillDefinition.query.filter(
        BillDefinition.user_id == user.id,
        BillDefinition.status == BillStatus.ACTIVE,
        BillDefinition.name.ilike(f"%{normalized}%"),
    ).all()

    if len(bills) == 0:
        return {"error": "not_found", "message": f"No bill matching '{name}' was found."}
    if len(bills) > 1:
        return {
            "error": "ambiguous",
            "message": "Multiple bills match that name. Ask the user which one they mean.",
            "matches": [{"bill_id": str(b.id), "name": b.name, "amount": str(b.default_amount)} for b in bills],
        }

    bill = bills[0]
    from app.models import BillOccurrence

    occurrence = (
        BillOccurrence.query.filter_by(bill_definition_id=bill.id, user_id=user.id, is_paid=False)
        .order_by(BillOccurrence.due_date.asc())
        .first()
    )
    if occurrence is None:
        return {"error": "no_unpaid_occurrence", "message": f"{bill.name} has no unpaid bill to mark as paid."}

    occ, new_occ, payment = bill_service.mark_occurrence_paid(user, occurrence.id)
    result = {"marked_paid": _occurrence_brief(occ, bill)}
    if new_occ is not None:
        result["next_occurrence"] = _occurrence_brief(new_occ, bill)
    return result


def _fn_get_monthly_spending(user) -> dict:
    total = dashboard_service.monthly_recurring_total(user)
    return {"monthly_recurring_total": str(total)}


def _fn_get_payment_history(user, month: str | None = None) -> dict:
    if not month:
        return {"error": "month_required", "message": "A month (YYYY-MM) is required."}
    date_from, date_to = history_service.parse_month(month)
    results = bill_service.query_occurrences(user, status="paid", date_from=date_from, date_to=date_to).limit(100).all()
    return {"bills": [_occurrence_brief(occ, bill) for occ, bill in results]}


def _fn_get_month_summary(user, month: str) -> dict:
    if not month:
        return {"error": "month_required", "message": "A month (YYYY-MM) is required."}
    summary = history_service.month_summary(user, month)
    return {
        "month": summary["month"],
        "expected_total": str(summary["expected_total"]),
        "paid_total": str(summary["paid_total"]),
        "outstanding_total": str(summary["outstanding_total"]),
    }


_DISPATCH = {
    "get_upcoming_bills": _fn_get_upcoming_bills,
    "get_overdue_bills": _fn_get_overdue_bills,
    "get_due_today_bills": _fn_get_due_today_bills,
    "get_paid_bills": _fn_get_paid_bills,
    "find_bill": _fn_find_bill,
    "mark_bill_paid": _fn_mark_bill_paid,
    "get_monthly_spending": _fn_get_monthly_spending,
    "get_payment_history": _fn_get_payment_history,
    "get_month_summary": _fn_get_month_summary,
}

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_upcoming_bills",
            "description": "Get the user's upcoming (not yet due) unpaid bills.",
            "parameters": {
                "type": "object",
                "properties": {"days": {"type": "integer", "description": "Look ahead this many days (default 30)."}},
            },
        },
    },
    {
        "type": "function",
        "function": {"name": "get_overdue_bills", "description": "Get the user's overdue unpaid bills.", "parameters": {"type": "object", "properties": {}}},
    },
    {
        "type": "function",
        "function": {"name": "get_due_today_bills", "description": "Get the user's bills due today.", "parameters": {"type": "object", "properties": {}}},
    },
    {
        "type": "function",
        "function": {
            "name": "get_paid_bills",
            "description": "Get the user's paid bills, optionally within one month.",
            "parameters": {"type": "object", "properties": {"month": {"type": "string", "description": "YYYY-MM, optional"}}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "find_bill",
            "description": "Search the user's active bills by name.",
            "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "mark_bill_paid",
            "description": "Mark a bill as paid by name. If multiple bills match, returns the matches so you can ask the user to clarify instead of guessing.",
            "parameters": {"type": "object", "properties": {"name": {"type": "string"}}, "required": ["name"]},
        },
    },
    {
        "type": "function",
        "function": {"name": "get_monthly_spending", "description": "Get the user's total monthly recurring spend.", "parameters": {"type": "object", "properties": {}}},
    },
    {
        "type": "function",
        "function": {
            "name": "get_payment_history",
            "description": "Get bills paid during a specific month.",
            "parameters": {"type": "object", "properties": {"month": {"type": "string", "description": "YYYY-MM"}}, "required": ["month"]},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_month_summary",
            "description": "Get expected/paid/outstanding totals for a specific month.",
            "parameters": {"type": "object", "properties": {"month": {"type": "string", "description": "YYYY-MM"}}, "required": ["month"]},
        },
    },
]


def run_assistant(user, user_message: str, history: list[dict] | None = None) -> dict:
    """
    Runs the tool-calling loop and returns {"reply": str, "actions": [...]}.
    `actions` records which functions were actually executed (for the
    frontend to e.g. refresh the dashboard after a mark-paid action).
    """
    if not isinstance(user_message, str) or not user_message.strip():
        raise ValidationError("message is required.")
    if len(user_message) > 2000:
        raise ValidationError("message is too long.")

    messages = list(history or [])
    messages.append({"role": "user", "content": user_message})

    actions_taken = []

    for _ in range(MAX_TOOL_ITERATIONS):
        assistant_message = run_assistant_turn(messages, TOOLS)
        tool_calls = getattr(assistant_message, "tool_calls", None)

        if not tool_calls:
            return {"reply": assistant_message.content or "", "actions": actions_taken}

        messages.append(
            {
                "role": "assistant",
                "content": assistant_message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in tool_calls
                ],
            }
        )

        for tool_call in tool_calls:
            fn_name = tool_call.function.name
            handler = _DISPATCH.get(fn_name)
            if handler is None:
                tool_result = {"error": "unknown_function"}
            else:
                import json as _json

                try:
                    args = _json.loads(tool_call.function.arguments or "{}")
                    if not isinstance(args, dict):
                        args = {}
                except _json.JSONDecodeError:
                    args = {}
                try:
                    tool_result = handler(user, **args)
                    actions_taken.append({"function": fn_name, "arguments": args})
                except TypeError as exc:
                    logger.warning("assistant_bad_arguments", extra={"extra_fields": {"function": fn_name}})
                    tool_result = {"error": "invalid_arguments"}
                except Exception as exc:  # a function failure must not crash the whole assistant turn
                    logger.error("assistant_function_failed", extra={"extra_fields": {"function": fn_name}}, exc_info=exc)
                    tool_result = {"error": "internal_error"}

            import json as _json

            messages.append({"role": "tool", "tool_call_id": tool_call.id, "content": _json.dumps(tool_result, default=str)})

    return {
        "reply": "I wasn't able to finish that request. Could you rephrase or simplify it?",
        "actions": actions_taken,
    }
