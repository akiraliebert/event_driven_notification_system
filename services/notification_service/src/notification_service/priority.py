"""Event type to notification priority mapping."""

from shared.enums import (
    OrderEventType,
    PaymentEventType,
    Priority,
    UserEventType,
)

_PRIORITY_MAP: dict[str, Priority] = {
    UserEventType.REGISTERED: Priority.NORMAL,
    OrderEventType.COMPLETED: Priority.HIGH,
    PaymentEventType.FAILED: Priority.CRITICAL,
}


def get_priority(event_type: str) -> Priority:
    """Return the notification priority for a given event type.

    Raises ValueError for unknown event types.
    """
    priority = _PRIORITY_MAP.get(event_type)
    if priority is None:
        raise ValueError(f"No priority mapping for event type: {event_type!r}")
    return priority
