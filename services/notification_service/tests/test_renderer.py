"""Tests for Jinja2 template rendering."""

import pytest
from jinja2 import UndefinedError

from notification_service.renderer import render_template


class TestRenderTemplate:
    def test_email_with_subject_and_body(self) -> None:
        body = render_template(
            "Hello {{ email }}, welcome!",
            {"email": "user@example.com"},
        )
        assert body == "Hello user@example.com, welcome!"

    def test_sms_without_subject(self) -> None:
        body = render_template(
            "Order #{{ order_id }} confirmed. Total: ${{ total_amount }}",
            {"order_id": "abc-123", "total_amount": "99.99"},
        )
        assert body == "Order #abc-123 confirmed. Total: $99.99"

    def test_uuid_slicing(self) -> None:
        order_id = "550e8400-e29b-41d4-a716-446655440000"
        body = render_template(
            "Order #{{ order_id[:8] }}", {"order_id": order_id}
        )
        assert body == "Order #550e8400"

    def test_strict_undefined_raises_on_missing_variable(self) -> None:
        with pytest.raises(UndefinedError):
            render_template("Hello {{ missing_var }}", {})
