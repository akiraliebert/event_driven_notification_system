"""Database layer: models, repositories, engine/session utilities."""

from shared.db.base import Base, create_db_engine, create_session_factory
from shared.db.models import Notification, NotificationTemplate, UserPreference
from shared.db.repositories import (
    NotificationRepository,
    TemplateRepository,
    UserPreferenceRepository,
)

__all__ = [
    "Base",
    "create_db_engine",
    "create_session_factory",
    "Notification",
    "NotificationTemplate",
    "UserPreference",
    "NotificationRepository",
    "TemplateRepository",
    "UserPreferenceRepository",
]
