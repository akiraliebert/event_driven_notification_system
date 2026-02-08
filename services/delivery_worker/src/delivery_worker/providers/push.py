"""Push notification delivery provider (dev stub)."""

import logging

from shared.db.models import Notification

from delivery_worker.providers.base import DeliveryProvider, DeliveryResult

logger = logging.getLogger(__name__)


class PushProvider(DeliveryProvider):
    """Stub push provider that logs instead of sending.

    Ready for integration with FCM/APNs — replace the send()
    body with actual API calls.
    """

    def send(self, notification: Notification) -> DeliveryResult:
        body = notification.content.get("body", "")
        preview = body[:50] if body else "(empty)"
        logger.info(
            "Push sent (stub)",
            extra={
                "notification_id": str(notification.id),
                "user_id": str(notification.user_id),
                "body_preview": preview,
            },
        )
        return DeliveryResult(success=True, details=f"Push delivered: {preview}")
