import uuid
from datetime import datetime

from sqlalchemy import String, DateTime, ForeignKey, Text, UniqueConstraint, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.mixins import UUIDPrimaryKeyMixin
from app.models.enums import NotificationType, NotificationChannel


class Notification(UUIDPrimaryKeyMixin, db.Model):
    """
    A record of a reminder that was actually sent. The unique constraint on
    (bill_occurrence_id, type, channel) is what the scheduler relies on to
    guarantee it never double-sends the same reminder, and the row's
    existence (or absence) is exactly how it knows what's left to send.
    """

    __tablename__ = "notifications"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bill_occurrence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bill_occurrences.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[NotificationType] = mapped_column(
        SAEnum(NotificationType, name="notification_type", native_enum=True), nullable=False
    )
    channel: Mapped[NotificationChannel] = mapped_column(
        SAEnum(NotificationChannel, name="notification_channel", native_enum=True), nullable=False
    )
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=db.func.now(), nullable=False
    )

    __table_args__ = (
        UniqueConstraint(
            "bill_occurrence_id", "type", "channel", name="uq_notification_occurrence_type_channel"
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Notification {self.type.value} {self.channel.value} occ={self.bill_occurrence_id}>"


class PushSubscription(UUIDPrimaryKeyMixin, db.Model):
    """A registered Web Push (VAPID) subscription for one browser/device."""

    __tablename__ = "push_subscriptions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    endpoint: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255), nullable=False)
    auth: Mapped[str] = mapped_column(String(255), nullable=False)
    user_agent: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=db.func.now(), nullable=False
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<PushSubscription {self.id} user={self.user_id}>"
