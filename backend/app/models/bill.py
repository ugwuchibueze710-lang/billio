import uuid
from datetime import date

from sqlalchemy import String, Numeric, Date, ForeignKey, Text, Index, Enum as SAEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.extensions import db
from app.models.mixins import UUIDPrimaryKeyMixin, TimestampMixin
from app.models.enums import RecurrenceType, BillStatus


class BillDefinition(UUIDPrimaryKeyMixin, TimestampMixin, db.Model):
    """
    The underlying recurring (or one-off) obligation, e.g. "Netflix, $17.99,
    monthly". Editing this changes FUTURE occurrences only -- past
    BillOccurrence/Payment rows keep their own snapshot amount so history is
    never rewritten retroactively (see occurrence.py).
    """

    __tablename__ = "bill_definitions"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    default_amount: Mapped[object] = mapped_column(Numeric(12, 2), nullable=False)
    recurrence: Mapped[RecurrenceType] = mapped_column(
        SAEnum(RecurrenceType, name="recurrence_type", native_enum=True), nullable=False
    )
    category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Invoice / account / customer reference number as printed on the bill,
    # if any -- purely informational (never used for auth/lookup), and
    # also used as a strong signal for duplicate detection when a new
    # document is uploaded (see app/services/extraction.check_existing_duplicates).
    reference_number: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # The anchor due date. For recurring bills, subsequent occurrences are
    # computed from this date using calendar-aware arithmetic (see
    # app/services/recurrence.py) so due-on-31st / leap-year / DST edge
    # cases are handled consistently rather than by naive date math.
    first_due_date: Mapped[date] = mapped_column(Date, nullable=False)

    status: Mapped[BillStatus] = mapped_column(
        SAEnum(BillStatus, name="bill_status", native_enum=True),
        nullable=False,
        default=BillStatus.ACTIVE,
    )

    user: Mapped["User"] = relationship(back_populates="bill_definitions")
    occurrences: Mapped[list["BillOccurrence"]] = relationship(
        back_populates="bill_definition", cascade="all, delete-orphan", order_by="BillOccurrence.due_date"
    )

    __table_args__ = (
        Index("ix_bill_definitions_user_status", "user_id", "status"),
    )

    @property
    def is_active(self) -> bool:
        return self.status == BillStatus.ACTIVE

    def __repr__(self) -> str:  # pragma: no cover
        return f"<BillDefinition {self.id} {self.name!r}>"
