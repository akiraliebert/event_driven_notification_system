"""Create notifications, notification_templates, user_preferences tables.

Revision ID: 0001
Revises: -
Create Date: 2026-02-08
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.Uuid, nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column(
            "priority", sa.String(16), nullable=False, server_default="normal"
        ),
        sa.Column(
            "status", sa.String(16), nullable=False, server_default="pending"
        ),
        sa.Column("source_event_id", sa.Uuid, nullable=False),
        sa.Column("source_event_type", sa.String(64), nullable=False),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("attempts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("next_retry_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("failed_reason", sa.Text, nullable=True),
        sa.UniqueConstraint(
            "source_event_id", "channel", name="uq_notification_event_channel"
        ),
    )
    op.create_index(
        "ix_notifications_user_id", "notifications", ["user_id"]
    )
    op.create_index(
        "ix_notifications_status", "notifications", ["status"]
    )
    op.create_index(
        "ix_notifications_next_retry_at", "notifications", ["next_retry_at"]
    )

    op.create_table(
        "notification_templates",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("subject_template", sa.Text, nullable=True),
        sa.Column("body_template", sa.Text, nullable=False),
        sa.Column(
            "is_active",
            sa.Boolean,
            nullable=False,
            server_default=sa.text("true"),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint(
            "event_type", "channel", name="uq_template_event_channel"
        ),
    )

    op.create_table(
        "user_preferences",
        sa.Column("user_id", sa.Uuid, primary_key=True),
        sa.Column("channels", JSONB, nullable=False),
        sa.Column("quiet_hours_start", sa.Time, nullable=True),
        sa.Column("quiet_hours_end", sa.Time, nullable=True),
        sa.Column(
            "timezone", sa.String(64), nullable=False, server_default="UTC"
        ),
    )


def downgrade() -> None:
    op.drop_table("user_preferences")
    op.drop_table("notification_templates")
    op.drop_index("ix_notifications_next_retry_at", table_name="notifications")
    op.drop_index("ix_notifications_status", table_name="notifications")
    op.drop_index("ix_notifications_user_id", table_name="notifications")
    op.drop_table("notifications")
