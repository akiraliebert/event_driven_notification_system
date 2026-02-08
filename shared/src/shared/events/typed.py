from typing import Any, Self

from pydantic import BaseModel, model_validator

from shared.enums import OrderEventType, PaymentEventType, UserEventType
from shared.events.base import EventMetadata
from shared.events.payloads import (
    OrderCompletedPayload,
    PaymentFailedPayload,
    UserRegisteredPayload,
)


class UserRegisteredEvent(BaseModel):
    metadata: EventMetadata
    payload: UserRegisteredPayload

    @model_validator(mode="before")
    @classmethod
    def _set_event_type(cls, data: Any) -> Any:
        if isinstance(data, dict):
            meta = data.setdefault("metadata", {})
            if isinstance(meta, dict):
                meta.setdefault("event_type", UserEventType.REGISTERED)
        return data

    @model_validator(mode="after")
    def _check_event_type(self) -> Self:
        if self.metadata.event_type != UserEventType.REGISTERED:
            raise ValueError(
                f"Expected event_type={UserEventType.REGISTERED!r}, "
                f"got {self.metadata.event_type!r}"
            )
        return self


class OrderCompletedEvent(BaseModel):
    metadata: EventMetadata
    payload: OrderCompletedPayload

    @model_validator(mode="before")
    @classmethod
    def _set_event_type(cls, data: Any) -> Any:
        if isinstance(data, dict):
            meta = data.setdefault("metadata", {})
            if isinstance(meta, dict):
                meta.setdefault("event_type", OrderEventType.COMPLETED)
        return data

    @model_validator(mode="after")
    def _check_event_type(self) -> Self:
        if self.metadata.event_type != OrderEventType.COMPLETED:
            raise ValueError(
                f"Expected event_type={OrderEventType.COMPLETED!r}, "
                f"got {self.metadata.event_type!r}"
            )
        return self


class PaymentFailedEvent(BaseModel):
    metadata: EventMetadata
    payload: PaymentFailedPayload

    @model_validator(mode="before")
    @classmethod
    def _set_event_type(cls, data: Any) -> Any:
        if isinstance(data, dict):
            meta = data.setdefault("metadata", {})
            if isinstance(meta, dict):
                meta.setdefault("event_type", PaymentEventType.FAILED)
        return data

    @model_validator(mode="after")
    def _check_event_type(self) -> Self:
        if self.metadata.event_type != PaymentEventType.FAILED:
            raise ValueError(
                f"Expected event_type={PaymentEventType.FAILED!r}, "
                f"got {self.metadata.event_type!r}"
            )
        return self


AnyTypedEvent = UserRegisteredEvent | OrderCompletedEvent | PaymentFailedEvent

_EVENT_REGISTRY: dict[str, type[BaseModel]] = {
    UserEventType.REGISTERED: UserRegisteredEvent,
    OrderEventType.COMPLETED: OrderCompletedEvent,
    PaymentEventType.FAILED: PaymentFailedEvent,
}


def parse_event(raw: dict[str, Any]) -> AnyTypedEvent:
    """Deserialize a raw dict (e.g. from Kafka) into a typed event.

    Raises ValueError if event_type is missing or unknown.
    """
    try:
        event_type = raw["metadata"]["event_type"]
    except (KeyError, TypeError) as exc:
        raise ValueError("Missing metadata.event_type in raw event") from exc

    event_cls = _EVENT_REGISTRY.get(event_type)
    if event_cls is None:
        raise ValueError(f"Unknown event type: {event_type!r}")

    return event_cls.model_validate(raw)  # type: ignore[return-value]
