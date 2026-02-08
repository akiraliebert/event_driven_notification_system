"""Abstract delivery provider interface."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from shared.db.models import Notification


@dataclass(frozen=True, slots=True)
class DeliveryResult:
    """Outcome of a delivery attempt."""

    success: bool
    details: str


class DeliveryProvider(ABC):
    """Base class for all channel delivery providers."""

    @abstractmethod
    def send(self, notification: Notification) -> DeliveryResult:
        """Attempt to deliver a notification.

        Implementations must not raise — return DeliveryResult(success=False)
        on failure instead.
        """
