from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserRegisteredPayload(BaseModel):
    user_id: UUID
    email: EmailStr


class OrderCompletedPayload(BaseModel):
    order_id: UUID
    user_id: UUID
    total_amount: Decimal


class PaymentFailedPayload(BaseModel):
    payment_id: UUID
    user_id: UUID
    reason: str
