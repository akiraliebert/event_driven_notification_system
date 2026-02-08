"""Email delivery provider (dev stub)."""

import logging

from shared.db.models import Notification

from delivery_worker.providers.base import DeliveryProvider, DeliveryResult

logger = logging.getLogger(__name__)


class EmailProvider(DeliveryProvider):
    """Stub email provider that logs instead of sending.

    Ready for integration with SMTP/SendGrid/SES — replace the send()
    body with actual API calls.
    """

    def send(self, notification: Notification) -> DeliveryResult:
        subject = notification.content.get("subject", "(no subject)")
        logger.info(
            "Email sent (stub)",
            extra={
                "notification_id": str(notification.id),
                "user_id": str(notification.user_id),
                "subject": subject,
            },
        )
        return DeliveryResult(success=True, details=f"Email delivered: {subject}")
