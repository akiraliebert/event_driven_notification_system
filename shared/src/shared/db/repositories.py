"""Data access repositories with constructor-injected sessions."""

import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from shared.db.models import Notification, NotificationTemplate, UserPreference
from shared.enums import Channel, NotificationStatus


class NotificationRepository:
    """Data access for the notifications table."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(self, notification: Notification) -> Notification:
        """Add a new notification and flush to populate server defaults."""
        self._session.add(notification)
        self._session.flush()
        return notification

    def get_by_id(self, notification_id: UUID) -> Notification | None:
        """Fetch a notification by primary key."""
        return self._session.get(Notification, notification_id)

    def get_by_event_id_and_channel(
        self, source_event_id: UUID, channel: str
    ) -> Notification | None:
        """Look up by (event_id, channel) for idempotency checks."""
        stmt = select(Notification).where(
            Notification.source_event_id == source_event_id,
            Notification.channel == channel,
        )
        return self._session.scalars(stmt).first()

    def get_channels_by_event_id(self, source_event_id: UUID) -> set[str]:
        """Get channels that already have notifications for this event.

        Used for idempotency: one query instead of N per-channel lookups.
        """
        stmt = select(Notification.channel).where(
            Notification.source_event_id == source_event_id,
        )
        return set(self._session.scalars(stmt).all())

    def update_status(
        self,
        notification_id: UUID,
        status: str,
        *,
        failed_reason: str | None = None,
        delivered_at: datetime.datetime | None = None,
        next_retry_at: datetime.datetime | None = None,
        increment_attempts: bool = False,
    ) -> Notification | None:
        """Update notification status and related fields.

        Returns the updated notification, or None if not found.
        """
        notification = self.get_by_id(notification_id)
        if notification is None:
            return None

        notification.status = status

        if failed_reason is not None:
            notification.failed_reason = failed_reason
        if delivered_at is not None:
            notification.delivered_at = delivered_at
        if next_retry_at is not None:
            notification.next_retry_at = next_retry_at
        if increment_attempts:
            notification.attempts += 1

        self._session.flush()
        return notification

    def get_pending_retries(
        self, now: datetime.datetime, limit: int = 100
    ) -> list[Notification]:
        """Fetch notifications due for retry.

        Selects where status in (PENDING, FAILED), next_retry_at <= now,
        attempts < max_attempts. Ordered oldest-first, capped by limit.
        """
        stmt = (
            select(Notification)
            .where(
                Notification.status.in_(
                    [NotificationStatus.PENDING, NotificationStatus.FAILED]
                ),
                Notification.next_retry_at <= now,
                Notification.attempts < Notification.max_attempts,
            )
            .order_by(Notification.next_retry_at.asc())
            .limit(limit)
        )
        return list(self._session.scalars(stmt).all())


class TemplateRepository:
    """Data access for notification templates."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_event_type_and_channel(
        self, event_type: str, channel: str
    ) -> NotificationTemplate | None:
        """Fetch a single active template for event_type + channel."""
        stmt = select(NotificationTemplate).where(
            NotificationTemplate.event_type == event_type,
            NotificationTemplate.channel == channel,
            NotificationTemplate.is_active.is_(True),
        )
        return self._session.scalars(stmt).first()

    def get_active_templates_for_event(
        self, event_type: str
    ) -> list[NotificationTemplate]:
        """Fetch all active templates for an event type (all channels)."""
        stmt = (
            select(NotificationTemplate)
            .where(
                NotificationTemplate.event_type == event_type,
                NotificationTemplate.is_active.is_(True),
            )
            .order_by(NotificationTemplate.channel)
        )
        return list(self._session.scalars(stmt).all())


class UserPreferenceRepository:
    """Data access for user notification preferences."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_user_id(self, user_id: UUID) -> UserPreference | None:
        """Fetch preferences for a user."""
        return self._session.get(UserPreference, user_id)

    def create_default(self, user_id: UUID) -> UserPreference:
        """Create default preferences: all channels enabled, UTC timezone."""
        preference = UserPreference(
            user_id=user_id,
            channels=[Channel.EMAIL, Channel.SMS, Channel.PUSH],
            timezone="UTC",
        )
        self._session.add(preference)
        self._session.flush()
        return preference
