import json
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError

from shared.enums import OrderEventType, PaymentEventType, UserEventType
from shared.events import (
    Event,
    EventMetadata,
    OrderCompletedEvent,
    OrderCompletedPayload,
    PaymentFailedEvent,
    PaymentFailedPayload,
    UserRegisteredEvent,
    UserRegisteredPayload,
    parse_event,
)


class TestEventMetadata:
    def test_auto_generated_fields(self):
        meta = EventMetadata(event_type=UserEventType.REGISTERED)
        assert isinstance(meta.event_id, UUID)
        assert meta.event_type == UserEventType.REGISTERED
        assert meta.occurred_at.tzinfo is not None
        assert meta.version == 1

    def test_explicit_fields(self):
        eid = uuid4()
        meta = EventMetadata(
            event_id=eid,
            event_type=OrderEventType.COMPLETED,
            version=2,
        )
        assert meta.event_id == eid
        assert meta.version == 2

    def test_invalid_event_type_rejected(self):
        with pytest.raises(ValidationError):
            EventMetadata(event_type="unknown.event")


class TestBaseEvent:
    def test_create_with_dict_payload(self):
        event = Event(
            metadata=EventMetadata(event_type=UserEventType.REGISTERED),
            payload={"user_id": str(uuid4()), "email": "test@example.com"},
        )
        assert event.payload["email"] == "test@example.com"


class TestUserRegisteredPayload:
    def test_valid(self):
        uid = uuid4()
        p = UserRegisteredPayload(user_id=uid, email="user@example.com")
        assert p.user_id == uid
        assert p.email == "user@example.com"

    def test_invalid_email(self):
        with pytest.raises(ValidationError):
            UserRegisteredPayload(user_id=uuid4(), email="not-an-email")

    def test_missing_user_id(self):
        with pytest.raises(ValidationError):
            UserRegisteredPayload(email="user@example.com")  # type: ignore[call-arg]


class TestOrderCompletedPayload:
    def test_valid(self):
        p = OrderCompletedPayload(
            order_id=uuid4(),
            user_id=uuid4(),
            total_amount=Decimal("99.99"),
        )
        assert p.total_amount == Decimal("99.99")

    def test_decimal_precision_preserved(self):
        p = OrderCompletedPayload(
            order_id=uuid4(),
            user_id=uuid4(),
            total_amount=Decimal("100.00"),
        )
        assert str(p.total_amount) == "100.00"

    def test_missing_fields(self):
        with pytest.raises(ValidationError):
            OrderCompletedPayload(order_id=uuid4())  # type: ignore[call-arg]


class TestPaymentFailedPayload:
    def test_valid(self):
        p = PaymentFailedPayload(
            payment_id=uuid4(),
            user_id=uuid4(),
            reason="Insufficient funds",
        )
        assert p.reason == "Insufficient funds"

    def test_empty_reason_allowed(self):
        p = PaymentFailedPayload(
            payment_id=uuid4(),
            user_id=uuid4(),
            reason="",
        )
        assert p.reason == ""


class TestTypedEvents:
    def test_user_registered_auto_metadata(self):
        uid = uuid4()
        event = UserRegisteredEvent(
            payload={"user_id": str(uid), "email": "a@b.com"},
        )
        assert event.metadata.event_type == UserEventType.REGISTERED
        assert event.payload.user_id == uid

    def test_order_completed_auto_metadata(self):
        event = OrderCompletedEvent(
            payload={
                "order_id": str(uuid4()),
                "user_id": str(uuid4()),
                "total_amount": "150.00",
            },
        )
        assert event.metadata.event_type == OrderEventType.COMPLETED
        assert event.payload.total_amount == Decimal("150.00")

    def test_payment_failed_auto_metadata(self):
        event = PaymentFailedEvent(
            payload={
                "payment_id": str(uuid4()),
                "user_id": str(uuid4()),
                "reason": "Card declined",
            },
        )
        assert event.metadata.event_type == PaymentEventType.FAILED

    def test_wrong_event_type_rejected(self):
        with pytest.raises(ValidationError, match="Expected event_type"):
            UserRegisteredEvent(
                metadata={"event_type": "order.completed"},
                payload={"user_id": str(uuid4()), "email": "a@b.com"},
            )

    def test_invalid_payload_rejected(self):
        with pytest.raises(ValidationError):
            UserRegisteredEvent(
                payload={"user_id": str(uuid4()), "email": "bad-email"},
            )


class TestSerialization:
    def test_event_roundtrip_json(self):
        uid = uuid4()
        original = UserRegisteredEvent(
            payload={"user_id": str(uid), "email": "test@example.com"},
        )
        json_str = original.model_dump_json()
        raw = json.loads(json_str)
        restored = UserRegisteredEvent.model_validate(raw)

        assert restored.metadata.event_id == original.metadata.event_id
        assert restored.metadata.event_type == original.metadata.event_type
        assert restored.payload.user_id == uid
        assert restored.payload.email == "test@example.com"

    def test_order_event_decimal_in_json(self):
        event = OrderCompletedEvent(
            payload={
                "order_id": str(uuid4()),
                "user_id": str(uuid4()),
                "total_amount": "249.95",
            },
        )
        json_str = event.model_dump_json()
        raw = json.loads(json_str)
        assert raw["payload"]["total_amount"] == "249.95"

    def test_model_dump_mode_python(self):
        event = UserRegisteredEvent(
            payload={"user_id": str(uuid4()), "email": "x@y.com"},
        )
        data = event.model_dump()
        assert isinstance(data["metadata"]["event_id"], UUID)
        assert isinstance(data["payload"]["user_id"], UUID)


class TestParseEvent:
    def test_parse_user_registered(self):
        uid = uuid4()
        raw = {
            "metadata": {"event_type": "user.registered"},
            "payload": {"user_id": str(uid), "email": "a@b.com"},
        }
        event = parse_event(raw)
        assert isinstance(event, UserRegisteredEvent)
        assert event.payload.user_id == uid

    def test_parse_order_completed(self):
        raw = {
            "metadata": {"event_type": "order.completed"},
            "payload": {
                "order_id": str(uuid4()),
                "user_id": str(uuid4()),
                "total_amount": "50.00",
            },
        }
        event = parse_event(raw)
        assert isinstance(event, OrderCompletedEvent)

    def test_parse_payment_failed(self):
        raw = {
            "metadata": {"event_type": "payment.failed"},
            "payload": {
                "payment_id": str(uuid4()),
                "user_id": str(uuid4()),
                "reason": "timeout",
            },
        }
        event = parse_event(raw)
        assert isinstance(event, PaymentFailedEvent)

    def test_unknown_event_type_raises(self):
        raw = {
            "metadata": {"event_type": "unknown.type"},
            "payload": {},
        }
        with pytest.raises(ValueError, match="Unknown event type"):
            parse_event(raw)

    def test_missing_metadata_raises(self):
        with pytest.raises(ValueError, match="Missing metadata.event_type"):
            parse_event({"payload": {}})

    def test_empty_dict_raises(self):
        with pytest.raises(ValueError, match="Missing metadata.event_type"):
            parse_event({})
