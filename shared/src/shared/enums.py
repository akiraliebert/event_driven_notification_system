from enum import StrEnum


class UserEventType(StrEnum):
    REGISTERED = "user.registered"


class OrderEventType(StrEnum):
    COMPLETED = "order.completed"


class PaymentEventType(StrEnum):
    FAILED = "payment.failed"


EventType = UserEventType | OrderEventType | PaymentEventType

ALL_EVENT_TYPES: set[str] = {
    e.value for enum_cls in (UserEventType, OrderEventType, PaymentEventType) for e in enum_cls
}


class Channel(StrEnum):
    EMAIL = "email"
    SMS = "sms"
    PUSH = "push"


class Priority(StrEnum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationStatus(StrEnum):
    PENDING = "pending"
    SENDING = "sending"
    DELIVERED = "delivered"
    FAILED = "failed"
