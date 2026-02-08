from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from shared.enums import OrderEventType, PaymentEventType, UserEventType


class EventMetadata(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: UserEventType | OrderEventType | PaymentEventType
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    version: int = 1


class Event(BaseModel):
    metadata: EventMetadata
    payload: dict[str, Any]
