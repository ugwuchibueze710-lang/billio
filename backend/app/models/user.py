import uuid
from datetime import datetime

from sqlalchemy import String, Boolean, DateTime, ForeignKey, Text, Index, Integer, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class User(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    """
    A Billio account. Signup requires only first_name + username + password --
    email is optional and, when present, unlocks password-reset-by-email and
    email reminders. Usernames and (if present) emails are unique
    case-insensitively via the functional indexes defined below.
    """

    __tablename__ = "users"

    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    username: Mapped[str] = mapped_column(String(30), nullable=False, unique=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="UTC")
    is_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Bumped on every password change / full logout-everywhere so previously
    # issued JWTs stop being honored immediately, independent of their
    # natural expiry (see app.utils.security.get_current_user).
    token_version: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    settings: Mapped["UserSettings"] = relationship(
        back_populates="user", uselist=False, cascade="all, delete-orphan"
    )
    bill_definitions: Mapped[list["BillDefinition"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_users_username_lower", func.lower(username), unique=True),
        Index(
            "ix_users_email_lower",
            func.lower(email),
            unique=True,
            postgresql_where=(email.isnot(None)),
        ),
    )

    def __repr__(self) -> str:  # pragma: no cover - debug helper only
        return f"<User {self.id} @{self.username}>"


class UserSettings(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    """Notification and reminder preferences. One row per user."""

    __tablename__ = "user_settings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )

    push_notifications: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_notifications: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    reminder_7_days: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    reminder_3_days: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reminder_1_day: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    reminder_due_today: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    overdue_reminders: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # True => notifications show "You have a bill due today" instead of
    # exposing the amount/name on a lock screen.
    private_notification_text: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    user: Mapped["User"] = relationship(back_populates="settings")


class PasswordResetToken(UUIDPrimaryKeyMixin, db.Model):
    """
    Single-use, short-lived password reset tokens. Only the SHA-256 hash of
    the token is stored -- the raw token is emailed to the user once and
    never persisted, so a database leak cannot be used to reset passwords.
    """

    __tablename__ = "password_reset_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_password_reset_tokens_user_id", "user_id"),)


class EmailVerificationToken(UUIDPrimaryKeyMixin, db.Model):
    """Single-use, short-lived tokens for confirming a newly added/changed
    email address before it is used for password reset or reminders."""

    __tablename__ = "email_verification_tokens"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_email_verification_tokens_user_id", "user_id"),)


class TokenBlocklist(db.Model):
    """
    Revoked JWTs (from logout or password change) so that access/refresh
    tokens issued before a security-relevant event stop working immediately,
    rather than remaining valid until their natural expiry.
    """

    __tablename__ = "token_blocklist"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    jti: Mapped[str] = mapped_column(String(36), nullable=False, unique=True, index=True)
    token_type: Mapped[str] = mapped_column(String(10), nullable=False)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    revoked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
