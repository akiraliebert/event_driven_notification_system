"""Seed notification templates (3 event types x 3 channels).

Revision ID: 0002
Revises: 0001
Create Date: 2026-02-08
"""

from uuid import uuid4

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

templates_table = sa.table(
    "notification_templates",
    sa.column("id", sa.Uuid),
    sa.column("event_type", sa.String),
    sa.column("channel", sa.String),
    sa.column("subject_template", sa.Text),
    sa.column("body_template", sa.Text),
    sa.column("is_active", sa.Boolean),
)

TEMPLATES = [
    # --- user.registered ---
    {
        "id": uuid4(),
        "event_type": "user.registered",
        "channel": "email",
        "subject_template": "Welcome to our platform!",
        "body_template": (
            "Hi there!\n\n"
            "Your account has been successfully created "
            "with the email {{ email }}.\n\n"
            "If you did not create this account, "
            "please contact support immediately.\n\n"
            "Best regards,\nThe Notification Team"
        ),
        "is_active": True,
    },
    {
        "id": uuid4(),
        "event_type": "user.registered",
        "channel": "sms",
        "subject_template": None,
        "body_template": (
            "Welcome! Your account ({{ email }}) has been created. "
            "Reply STOP to opt out of SMS notifications."
        ),
        "is_active": True,
    },
    {
        "id": uuid4(),
        "event_type": "user.registered",
        "channel": "push",
        "subject_template": None,
        "body_template": (
            '{"title": "Welcome!", '
            '"body": "Your account is ready. Tap to complete your profile.", '
            '"action": "open_profile"}'
        ),
        "is_active": True,
    },
    # --- order.completed ---
    {
        "id": uuid4(),
        "event_type": "order.completed",
        "channel": "email",
        "subject_template": "Order confirmed — #{{ order_id[:8] }}",
        "body_template": (
            "Hello!\n\n"
            "Your order #{{ order_id[:8] }} has been confirmed.\n\n"
            "Order total: ${{ total_amount }}\n\n"
            "You will receive a shipping notification "
            "once your order is dispatched.\n\n"
            "Thank you for your purchase!"
        ),
        "is_active": True,
    },
    {
        "id": uuid4(),
        "event_type": "order.completed",
        "channel": "sms",
        "subject_template": None,
        "body_template": (
            "Order #{{ order_id[:8] }} confirmed! "
            "Total: ${{ total_amount }}. "
            "We'll notify you when it ships."
        ),
        "is_active": True,
    },
    {
        "id": uuid4(),
        "event_type": "order.completed",
        "channel": "push",
        "subject_template": None,
        "body_template": (
            '{"title": "Order Confirmed", '
            '"body": "Order #{{ order_id[:8] }} for ${{ total_amount }} is confirmed.", '
            '"action": "open_order", '
            '"data": {"order_id": "{{ order_id }}"}}'
        ),
        "is_active": True,
    },
    # --- payment.failed ---
    {
        "id": uuid4(),
        "event_type": "payment.failed",
        "channel": "email",
        "subject_template": "Payment issue — action required",
        "body_template": (
            "Hello,\n\n"
            "We were unable to process your payment.\n\n"
            "Reason: {{ reason }}\n"
            "Payment reference: {{ payment_id[:8] }}\n\n"
            "Please update your payment method or try again.\n"
            "If you believe this is an error, contact our support team.\n\n"
            "Regards,\nThe Billing Team"
        ),
        "is_active": True,
    },
    {
        "id": uuid4(),
        "event_type": "payment.failed",
        "channel": "sms",
        "subject_template": None,
        "body_template": (
            "Payment failed: {{ reason }}. "
            "Ref: {{ payment_id[:8] }}. "
            "Please update your payment method."
        ),
        "is_active": True,
    },
    {
        "id": uuid4(),
        "event_type": "payment.failed",
        "channel": "push",
        "subject_template": None,
        "body_template": (
            '{"title": "Payment Failed", '
            '"body": "{{ reason }}. Tap to update your payment method.", '
            '"action": "open_billing", '
            '"data": {"payment_id": "{{ payment_id }}"}}'
        ),
        "is_active": True,
    },
]


def upgrade() -> None:
    op.bulk_insert(templates_table, TEMPLATES)


def downgrade() -> None:
    for tpl in TEMPLATES:
        op.execute(
            templates_table.delete().where(templates_table.c.id == tpl["id"])
        )
