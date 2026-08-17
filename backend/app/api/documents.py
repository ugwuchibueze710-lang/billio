from flask import Blueprint, jsonify

from app.errors import NotFoundError
from app.models import BillDocument
from app.schemas import serialize_document
from app.services.storage import generate_download_url
from app.utils.security import get_current_user

bp = Blueprint("documents", __name__, url_prefix="/api/documents")


def _get_owned_document(user, document_id) -> BillDocument:
    doc = BillDocument.query.filter_by(id=document_id, user_id=user.id).first()
    if doc is None:
        raise NotFoundError("Document not found.")
    return doc


@bp.get("/<uuid:document_id>")
def get_document(document_id):
    user = get_current_user()
    doc = _get_owned_document(user, document_id)
    return jsonify({"document": serialize_document(doc)}), 200


@bp.get("/<uuid:document_id>/download-url")
def get_download_url(document_id):
    user = get_current_user()
    doc = _get_owned_document(user, document_id)
    url = generate_download_url(doc.storage_key)
    return jsonify({"url": url, "expires_in_seconds": 300}), 200
