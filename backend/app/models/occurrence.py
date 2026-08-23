import uuid
from datetime import date, datetime

from sqlalchemy import String, Numeric, Date, DateTime, Boolean, ForeignKey, Text, Index, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin


class BillOccurrence(UUIDPrimaryKeyMixin, db.Model):
    """
    A single expected payment instance of a bill (e.g. "Netflix due Aug 20").
    Recurring bills generate a new occurrence each cycle rather than
    overwriting a single row, which is what preserves accurate payment
    history. `amount` is a snapshot taken at creation time -- later edits to
    the parent BillDefinition's default_amount never rewrite past occurrences.

    Status (upcoming / due today / overdue / paid) is intentionally NOT a
    stored column. It is derived at read time from `due_date`, `is_paid`,
    and the user's timezone (see app/services/status.py) so it can never
    drift out of sync with "today".
    """

    __tablename__ = "bill_occurrences"

    bill_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bill_definitions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_paid: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)
    paid_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=db.func.now(), nullable=False
    )

    bill_definition: Mapped["BillDefinition"] = relationship(back_populates="occurrences")
    payment: Mapped["Payment"] = relationship(back_populates="occurrence", uselist=False)
    documents: Mapped[list["BillDocument"]] = relationship(back_populates="bill_occurrence")

    __table_args__ = (
        Index("ix_bill_occurrences_user_due", "user_id", "due_date"),
        Index("ix_bill_occurrences_user_paid", "user_id", "is_paid"),
        # A bill definition should never have two occurrences for the same
        # due date -- prevents accidental double-generation.
        UniqueConstraint("bill_definition_id", "due_date", name="uq_bill_occurrence_def_due_date"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BillOccurrence {self.id} due={self.due_date} paid={self.is_paid}>"


class Payment(UUIDPrimaryKeyMixin, db.Model):
    """
    An immutable record of a completed payment. Fully denormalized
    (bill name/category/amount snapshotted) so that later edits or even
    deletion of the parent BillDefinition can never alter historical
    financial records -- this table is the durable audit trail referenced
    throughout the product spec.
    """

    __tablename__ = "payments"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    bill_occurrence_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("bill_occurrences.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    bill_definition_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("bill_definitions.id", ondelete="SET NULL"), nullable=True, index=True
    )

    amount_paid: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    due_date: Mapped[date] = mapped_column(Date, nullable=False)
    paid_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)

    bill_name: Mapped[str] = mapped_column(String(200), nullable=False)
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=db.func.now(), nullable=False
    )

    occurrence: Mapped["BillOccurrence"] = relationship(back_populates="payment")

    __table_args__ = (
        Index("ix_payments_user_paid_at", "user_id", "paid_at"),
        Index("ix_payments_user_category", "user_id", "category"),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Payment {self.id} {self.bill_name!r} {self.amount_paid}>"
