import csv
import io
import logging
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify

from app.extensions import db
from app.errors import AuthenticationError
from app.models import BillOccurrence, BillDefinition, BillDocument
from app.services import supabase_admin
from app.services.storage import delete_object
from app.utils.security import get_current_user
from app.utils.validation import get_json_body, require_fields

logger = logging.getLogger("billio.account")

bp = Blueprint("account", __name__, url_prefix="/api/account")


@bp.get("/export")
def export_csv():
    user = get_current_user()

    rows = (
        db.session.query(BillOccurrence, BillDefinition)
        .join(BillDefinition, BillOccurrence.bill_definition_id == BillDefinition.id)
        .filter(BillOccurrence.user_id == user.id)
        .order_by(BillOccurrence.due_date.asc())
        .all()
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        ["bill_name", "category", "recurrence", "amount", "due_date", "status", "paid_at", "created_at"]
    )
    from app.services.status import compute_status, user_today

    today = user_today(user.timezone)
    for occ, bill in rows:
        writer.writerow(
            [
                bill.name,
                bill.category or "",
                bill.recurrence.value,
                str(occ.amount),
                occ.due_date.isoformat(),
                compute_status(occ.due_date, occ.is_paid, today),
                occ.paid_at.isoformat() if occ.paid_at else "",
                occ.created_at.isoformat(),
            ]
        )

    csv_data = buffer.getvalue()
    filename = f"billio-export-{datetime.now(timezone.utc).strftime('%Y%m%d')}.csv"
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@bp.delete("")
def delete_account():
    user = get_current_user()
    body = get_json_body()
    require_fields(body, "password")

    try:
        supabase_admin.sign_in_with_password(user.supabase_login_email, body.get("password"))
    except AuthenticationError:
        raise AuthenticationError("Incorrect password.")

    documents = BillDocument.query.filter_by(user_id=user.id).all()
    for doc in documents:
        delete_object(doc.storage_key)

    user_id = user.id
    supabase_user_id = user.supabase_user_id
    db.session.delete(user)  # cascades to bills, occurrences, payments, documents, notifications, feedback, etc.
    db.session.commit()
    supabase_admin.admin_delete_user(supabase_user_id)  # best-effort; logs and continues on failure

    logger.info("account_deleted", extra={"extra_fields": {"user_id": str(user_id)}})
    return jsonify({"message": "Your account and all associated data have been permanently deleted."}), 200
