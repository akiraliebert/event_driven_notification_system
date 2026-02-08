"""SQLAlchemy ORM models for the notification system."""

import datetime
import uuid

from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    String,
    Text,
    Time,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from shared.db.base import Base
from shared.db.types import JSONBCompatible
from shared.enums import NotificationStatus, Priority


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    priority: Mapped[str] = mapped_column(
        String(16), nullable=False, default=Priority.NORMAL
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default=NotificationStatus.PENDING, index=True
    )
    source_event_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    source_event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    content: Mapped[dict] = mapped_column(JSONBCompatible, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=3)
    next_retry_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True, index=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    delivered_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    failed_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint(
            "source_event_id", "channel", name="uq_notification_event_channel"
        ),
    )


class NotificationTemplate(Base):
    __tablename__ = "notification_templates"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid, primary_key=True, default=uuid.uuid4
    )
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    channel: Mapped[str] = mapped_column(String(16), nullable=False)
    subject_template: Mapped[str | None] = mapped_column(Text, nullable=True)
    body_template: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "event_type", "channel", name="uq_template_event_channel"
        ),
    )


class UserPreference(Base):
    __tablename__ = "user_preferences"

    user_id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    channels: Mapped[list] = mapped_column(JSONBCompatible, nullable=False)
    quiet_hours_start: Mapped[datetime.time | None] = mapped_column(
        Time, nullable=True
    )
    quiet_hours_end: Mapped[datetime.time | None] = mapped_column(
        Time, nullable=True
    )
    timezone: Mapped[str] = mapped_column(
        String(64), nullable=False, default="UTC"
    )
