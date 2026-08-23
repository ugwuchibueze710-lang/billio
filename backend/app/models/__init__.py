"""
Import every model here so that:
  1. `from app.models import User, BillDefinition, ...` works everywhere else.
  2. Alembic's autogenerate can see the full metadata via app.extensions.db.
"""
from app.models.user import (
    User,
    UserSettings,
    PasswordResetToken,
    EmailVerificationToken,
)
from app.models.bill import BillDefinition
from app.models.occurrence import BillOccurrence, Payment
from app.models.document import BillDocument
from app.models.notification import Notification, PushSubscription
from app.models.feedback import Feedback
from app.models.audit_log import AdminAuditLog
from app.models.enums import (
    RecurrenceType,
    BillStatus,
    NotificationType,
    NotificationChannel,
    FeedbackType,
    FeedbackStatus,
    SUGGESTED_CATEGORIES,
)

__all__ = [
    "User",
    "UserSettings",
    "PasswordResetToken",
    "EmailVerificationToken",
    "BillDefinition",
    "BillOccurrence",
    "Payment",
    "BillDocument",
    "Notification",
    "PushSubscription",
    "Feedback",
    "AdminAuditLog",
    "RecurrenceType",
    "BillStatus",
    "NotificationType",
    "NotificationChannel",
    "FeedbackType",
    "FeedbackStatus",
    "SUGGESTED_CATEGORIES",
]
