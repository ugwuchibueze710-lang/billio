import uuid
from datetime import datetime

from sqlalchemy import String, Integer, ForeignKey, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.mixins import UUIDPrimaryKeyMixin


class BillDocument(UUIDPrimaryKeyMixin, db.Model):
    """
    Metadata for a user-uploaded bill photo. The actual image bytes live in
    object storage (R2), never in Postgres -- `storage_key` is an opaque,
    per-user-namespaced key that only the backend resolves to a signed URL
    after verifying the requester owns the document.
    """

    __tablename__ = "bill_documents"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bill_definition_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bill_definitions.id", ondelete="SET NULL"), nullable=True, index=True
    )
    bill_occurrence_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bill_occurrences.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # NOT unique: when one uploaded file (PDF or multi-bill photo) contains
    # several distinct bills, extraction creates one BillDocument metadata
    # row PER bill, all sharing the same storage_key -- so every resulting
    # bill still links back to the one real uploaded file (see
    # app/api/ai.py's _extract_and_store_bills), without duplicating the
    # actual stored bytes.
    storage_key: Mapped[str] = mapped_column(String(500), nullable=False, index=True)
    file_type: Mapped[str] = mapped_column(String(50), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=db.func.now(), nullable=False
    )

    bill_occurrence: Mapped["BillOccurrence"] = relationship(back_populates="documents")

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BillDocument {self.id} {self.storage_key}>"
