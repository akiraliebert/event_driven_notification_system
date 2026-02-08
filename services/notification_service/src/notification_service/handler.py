"""Event handler — orchestrates notification creation from domain events."""

import logging
from typing import Any
from uuid import UUID

from celery import Celery
from sqlalchemy.orm import Session, sessionmaker

from shared.db.models import Notification
from shared.db.repositories import (
    NotificationRepository,
    TemplateRepository,
    UserPreferenceRepository,
)
from shared.enums import Channel, NotificationStatus
from shared.events.typed import AnyTypedEvent, parse_event

from notification_service.priority import get_priority
from notification_service.producer import KafkaStatusProducer
from notification_service.quiet_hours import calculate_eta
from notification_service.renderer import render_template

logger = logging.getLogger(__name__)


class EventHandler:
    """Processes domain events and creates notification delivery tasks."""

    def __init__(
        self,
        session_factory: sessionmaker[Session],
        celery_app: Celery,
        status_producer: KafkaStatusProducer,
    ) -> None:
        self._session_factory = session_factory
        self._celery = celery_app
        self._status_producer = status_producer

    def handle(self, raw_event: dict[str, Any]) -> None:
        """Process a single raw event from Kafka.

        Creates notifications for all applicable channels in a single
        DB transaction, dispatches Celery tasks, and publishes status events.
        """
        event = parse_event(raw_event)
        event_id = event.metadata.event_id
        event_type = str(event.metadata.event_type)
        user_id = self._extract_user_id(event)
        priority = get_priority(event_type)
        payload_dict = event.payload.model_dump()

        log_ctx = {
            "event_id": str(event_id),
            "event_type": event_type,
            "user_id": str(user_id),
        }

        created_notifications: list[Notification] = []

        with self._session_factory() as session:
            notification_repo = NotificationRepository(session)
            template_repo = TemplateRepository(session)
            pref_repo = UserPreferenceRepository(session)

            # Idempotency: skip already-processed channels
            existing_channels = notification_repo.get_channels_by_event_id(event_id)
            if existing_channels:
                logger.info(
                    "Partial reprocessing — some channels already handled",
                    extra={**log_ctx, "existing_channels": sorted(existing_channels)},
                )

            # Get user preferences (create defaults if missing)
            preferences = pref_repo.get_by_user_id(user_id)
            if preferences is None:
                preferences = pref_repo.create_default(user_id)
                logger.info("Created default preferences", extra=log_ctx)

            enabled_channels: set[str] = set(preferences.channels)

            # Get active templates for this event type
            templates = template_repo.get_active_templates_for_event(event_type)

            for template in templates:
                channel = template.channel

                # Skip already-processed channels (idempotency)
                if channel in existing_channels:
                    continue

                # Skip disabled channels (user preference)
                if channel not in enabled_channels:
                    logger.info(
                        "Channel disabled by user preference",
                        extra={**log_ctx, "channel": channel},
                    )
                    continue

                # Render content
                content = self._render_content(template, payload_dict)
                if content is None:
                    logger.warning(
                        "Template rendering failed, skipping channel",
                        extra={**log_ctx, "channel": channel},
                    )
                    continue

                # Calculate quiet hours ETA
                eta = calculate_eta(
                    preferences.quiet_hours_start,
                    preferences.quiet_hours_end,
                    preferences.timezone,
                )

                notification = Notification(
                    user_id=user_id,
                    channel=channel,
                    priority=priority,
                    status=NotificationStatus.PENDING,
                    source_event_id=event_id,
                    source_event_type=event_type,
                    content=content,
                )
                notification_repo.create(notification)
                created_notifications.append(notification)

                # Dispatch Celery task
                task_kwargs = {"notification_id": str(notification.id)}
                celery_kwargs: dict[str, Any] = {"queue": priority}
                if eta is not None:
                    celery_kwargs["eta"] = eta
                    logger.info(
                        "Deferred delivery due to quiet hours",
                        extra={**log_ctx, "channel": channel, "eta": str(eta)},
                    )

                self._celery.send_task(
                    "delivery_worker.tasks.send_notification",
                    kwargs=task_kwargs,
                    **celery_kwargs,
                )

            session.commit()

        # Publish status events after successful commit
        for n in created_notifications:
            self._status_producer.publish_status(
                notification_id=n.id,
                status=n.status,
                event_type=event_type,
                channel=n.channel,
                user_id=user_id,
            )

        logger.info(
            "Event processed",
            extra={
                **log_ctx,
                "notifications_created": len(created_notifications),
                "channels": [n.channel for n in created_notifications],
            },
        )

    @staticmethod
    def _extract_user_id(event: AnyTypedEvent) -> UUID:
        """Extract user_id from any typed event payload."""
        return event.payload.user_id

    @staticmethod
    def _render_content(
        template: Any, payload_dict: dict[str, Any]
    ) -> dict[str, str] | None:
        """Render notification content from a template.

        Returns a dict with 'body' and optionally 'subject', or None on error.
        """
        try:
            content: dict[str, str] = {
                "body": render_template(template.body_template, payload_dict),
            }
            if template.subject_template:
                content["subject"] = render_template(
                    template.subject_template, payload_dict
                )
            return content
        except Exception:
            logger.exception("Failed to render template %s", template.id)
            return None
