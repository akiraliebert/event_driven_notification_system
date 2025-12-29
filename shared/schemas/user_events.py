from uuid import UUID

from pydantic import BaseModel, EmailStr


class UserRegisteredPayload(BaseModel):
    user_id: UUID
    email: EmailStr
