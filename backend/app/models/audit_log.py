import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.extensions import db
from app.models.mixins import UUIDPrimaryKeyMixin


class AdminAuditLog(UUIDPrimaryKeyMixin, db.Model):
    """
    Records administrative actions (status changes, notes, views) on
    sensitive resources like feedback. `metadata_json` must only ever hold
    small, non-sensitive structured data (e.g. {"old_status": "new",
    "new_status": "reviewing"}) -- never full feedback message text, bill
    contents, or credentials.
    """

    __tablename__ = "admin_audit_log"

    actor_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    target_type: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=db.func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AdminAuditLog {self.action} target={self.target_type}:{self.target_id}>"
