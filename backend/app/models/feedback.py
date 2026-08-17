import uuid
from datetime import datetime

from sqlalchemy import Text, Integer, ForeignKey, CheckConstraint, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin
from app.models.enums import FeedbackType, FeedbackStatus


class Feedback(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    """
    A user-submitted feedback item. Deliberately minimal: no denormalized
    copy of the user's email/name/financial data is stored here. The
    submitting account is identified purely via user_id, resolved through
    the authenticated session -- never trusted from client input.
    """

    __tablename__ = "feedback"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[FeedbackType] = mapped_column(
        SAEnum(FeedbackType, name="feedback_type", native_enum=True), nullable=False
    )
    message: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[FeedbackStatus] = mapped_column(
        SAEnum(FeedbackStatus, name="feedback_status", native_enum=True),
        nullable=False,
        default=FeedbackStatus.NEW,
        index=True,
    )
    # Internal-only. Must never be serialized in any non-admin API response.
    admin_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        CheckConstraint("rating IS NULL OR (rating >= 1 AND rating <= 5)", name="ck_feedback_rating_range"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Feedback {self.id} {self.type.value} status={self.status.value}>"
