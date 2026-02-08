"""Celery task for notification delivery."""

import logging
from datetime import datetime, timezone
from uuid import UUID

from shared.db.repositories import NotificationRepository
from shared.enums import NotificationStatus

from delivery_worker.celery import app
from delivery_worker.config import DeliveryConfig
from delivery_worker.providers import ProviderRegistry
from delivery_worker.rate_limiter import RateLimiter
from delivery_worker.status_publisher import KafkaStatusPublisher

logger = logging.getLogger(__name__)

_RATE_LIMIT_RETRY_SECONDS = 10


@app.task(name="delivery_worker.tasks.send_notification")
def send_notification(notification_id: str) -> None:
    """Deliver a single notification.

    This task is dispatched by the notification service with a
    ``notification_id`` string.  It loads the notification from the DB,
    checks idempotency / rate limits, calls the appropriate provider,
    and updates the status accordingly.
    """
    session_factory = app.conf._session_factory
    provider_registry: ProviderRegistry = app.conf._provider_registry
    rate_limiter: RateLimiter = app.conf._rate_limiter
    status_publisher: KafkaStatusPublisher = app.conf._status_publisher
    delivery_config: DeliveryConfig = app.conf._delivery_config

    nid = UUID(notification_id)

    with session_factory() as session:
        repo = NotificationRepository(session)
        notification = repo.get_by_id(nid)

        if notification is None:
            logger.warning(
                "Notification not found, skipping",
                extra={"notification_id": notification_id},
            )
            return

        log_ctx = {
            "notification_id": notification_id,
            "channel": notification.channel,
            "attempt": notification.attempts,
        }

        # Idempotency: skip terminal states
        if notification.status == NotificationStatus.DELIVERED:
            logger.info("Already delivered, skipping", extra=log_ctx)
            return
        if (
            notification.status == NotificationStatus.FAILED
            and notification.attempts >= notification.max_attempts
        ):
            logger.info("Already permanently failed, skipping", extra=log_ctx)
            return

        # Transition to SENDING
        repo.update_status(nid, NotificationStatus.SENDING)
        session.commit()

        # Rate limit check
        if not rate_limiter.acquire(notification.channel):
            logger.info("Rate limited, rescheduling", extra=log_ctx)
            repo.update_status(nid, NotificationStatus.PENDING)
            session.commit()
            _requeue(notification_id, _RATE_LIMIT_RETRY_SECONDS)
            return

        # Deliver via provider
        try:
            provider = provider_registry.get(notification.channel)
            result = provider.send(notification)
        except Exception:
            logger.exception("Provider error", extra=log_ctx)
            result = None

        if result is not None and result.success:
            now = datetime.now(timezone.utc)
            repo.update_status(
                nid,
                NotificationStatus.DELIVERED,
                delivered_at=now,
            )
            session.commit()
            logger.info(
                "Delivery succeeded",
                extra={**log_ctx, "result": result.details},
            )
            status_publisher.publish_status(
                notification_id=nid,
                status=NotificationStatus.DELIVERED,
                event_type=notification.source_event_type,
                channel=notification.channel,
                user_id=notification.user_id,
            )
            return

        # Failure path
        error_reason = result.details if result is not None else "Provider exception"
        new_attempts = notification.attempts + 1
        log_ctx["attempt"] = new_attempts

        if new_attempts < notification.max_attempts:
            backoff = _get_backoff(new_attempts, delivery_config.retry_backoff_seconds)
            retry_at = datetime.now(timezone.utc)
            repo.update_status(
                nid,
                NotificationStatus.PENDING,
                next_retry_at=retry_at,
                increment_attempts=True,
            )
            session.commit()
            logger.warning(
                "Delivery failed, scheduling retry",
                extra={**log_ctx, "backoff_seconds": backoff, "reason": error_reason},
            )
            _requeue(notification_id, backoff)
        else:
            repo.update_status(
                nid,
                NotificationStatus.FAILED,
                failed_reason=error_reason,
                increment_attempts=True,
            )
            session.commit()
            logger.error(
                "Delivery permanently failed",
                extra={**log_ctx, "reason": error_reason},
            )
            status_publisher.publish_status(
                notification_id=nid,
                status=NotificationStatus.FAILED,
                event_type=notification.source_event_type,
                channel=notification.channel,
                user_id=notification.user_id,
            )


def _requeue(notification_id: str, countdown: int) -> None:
    """Re-enqueue the task with a delay."""
    app.send_task(
        "delivery_worker.tasks.send_notification",
        kwargs={"notification_id": notification_id},
        countdown=countdown,
    )


def _get_backoff(attempt: int, schedule: list[int]) -> int:
    """Return backoff seconds for the given attempt number (1-based).

    Falls back to the last value in *schedule* when attempt exceeds the
    length of the list.
    """
    idx = min(attempt - 1, len(schedule) - 1)
    return schedule[idx]
