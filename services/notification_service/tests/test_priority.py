"""Tests for event type → priority mapping."""

import pytest

from shared.enums import (
    OrderEventType,
    PaymentEventType,
    Priority,
    UserEventType,
)

from notification_service.priority import get_priority


class TestGetPriority:
    def test_user_registered_is_normal(self) -> None:
        assert get_priority(UserEventType.REGISTERED) == Priority.NORMAL

    def test_order_completed_is_high(self) -> None:
        assert get_priority(OrderEventType.COMPLETED) == Priority.HIGH

    def test_payment_failed_is_critical(self) -> None:
        assert get_priority(PaymentEventType.FAILED) == Priority.CRITICAL

    def test_unknown_event_type_raises(self) -> None:
        with pytest.raises(ValueError, match="No priority mapping"):
            get_priority("unknown.event")
