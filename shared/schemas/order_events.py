from uuid import UUID

from pydantic import BaseModel


class OrderCompletedPayload(BaseModel):
    order_id: UUID
    user_id: UUID
    total_amount: float
