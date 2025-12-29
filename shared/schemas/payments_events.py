from uuid import UUID

from pydantic import BaseModel


class PaymentFailedPayload(BaseModel):
    payment_id: UUID
    user_id: UUID
    reason: str
