import enum


class RecurrenceType(str, enum.Enum):
    NONE = "none"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    YEARLY = "yearly"


class BillStatus(str, enum.Enum):
    """Lifecycle status of a bill definition (not the same as an occurrence's
    paid/overdue state, which is computed, not stored)."""

    ACTIVE = "active"
    CANCELLED = "cancelled"


class NotificationType(str, enum.Enum):
    REMINDER_7_DAY = "reminder_7_day"
    REMINDER_3_DAY = "reminder_3_day"
    REMINDER_1_DAY = "reminder_1_day"
    REMINDER_DUE_TODAY = "reminder_due_today"
    REMINDER_OVERDUE_1 = "reminder_overdue_1"
    REMINDER_OVERDUE_2 = "reminder_overdue_2"
    REMINDER_OVERDUE_3 = "reminder_overdue_3"


class NotificationChannel(str, enum.Enum):
    PUSH = "push"
    EMAIL = "email"


class FeedbackType(str, enum.Enum):
    REVIEW = "review"
    BUG = "bug"
    IMPROVEMENT = "improvement"
    FEATURE_REQUEST = "feature_request"
    OTHER = "other"


class FeedbackStatus(str, enum.Enum):
    NEW = "new"
    REVIEWING = "reviewing"
    PLANNED = "planned"
    RESOLVED = "resolved"
    DISMISSED = "dismissed"


SUGGESTED_CATEGORIES = [
    "utilities",
    "housing",
    "insurance",
    "entertainment",
    "phone",
    "internet",
    "subscription",
    "transportation",
    "health",
    "debt",
    "other",
]
