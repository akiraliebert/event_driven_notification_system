from shared.enums import (
    ALL_EVENT_TYPES,
    Channel,
    NotificationStatus,
    OrderEventType,
    PaymentEventType,
    Priority,
    UserEventType,
)


class TestEventTypes:
    def test_user_event_type_value(self):
        assert UserEventType.REGISTERED == "user.registered"

    def test_order_event_type_value(self):
        assert OrderEventType.COMPLETED == "order.completed"

    def test_payment_event_type_value(self):
        assert PaymentEventType.FAILED == "payment.failed"

    def test_event_types_are_strings(self):
        assert isinstance(UserEventType.REGISTERED, str)
        assert isinstance(OrderEventType.COMPLETED, str)
        assert isinstance(PaymentEventType.FAILED, str)

    def test_all_event_types_set(self):
        assert ALL_EVENT_TYPES == {
            "user.registered",
            "order.completed",
            "payment.failed",
        }


class TestChannel:
    def test_values(self):
        assert Channel.EMAIL == "email"
        assert Channel.SMS == "sms"
        assert Channel.PUSH == "push"

    def test_is_string(self):
        assert isinstance(Channel.EMAIL, str)

    def test_members_count(self):
        assert len(Channel) == 3


class TestPriority:
    def test_values(self):
        assert Priority.LOW == "low"
        assert Priority.NORMAL == "normal"
        assert Priority.HIGH == "high"
        assert Priority.CRITICAL == "critical"

    def test_members_count(self):
        assert len(Priority) == 4


class TestNotificationStatus:
    def test_values(self):
        assert NotificationStatus.PENDING == "pending"
        assert NotificationStatus.SENDING == "sending"
        assert NotificationStatus.DELIVERED == "delivered"
        assert NotificationStatus.FAILED == "failed"

    def test_members_count(self):
        assert len(NotificationStatus) == 4
