from typing import Literal

UserEventType = Literal[
    "user.registered",
]

OrderEventType = Literal[
    "order.completed",
]

PaymentEventType = Literal[
    "payment.failed",
]

EventType = UserEventType | OrderEventType | PaymentEventType
