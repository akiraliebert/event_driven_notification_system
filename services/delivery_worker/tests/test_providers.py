"""Tests for delivery providers and the provider registry."""

import uuid

import pytest

from shared.db.models import Notification
from shared.enums import Channel, NotificationStatus, Priority

from delivery_worker.providers import ProviderRegistry, create_default_registry
from delivery_worker.providers.email import EmailProvider
from delivery_worker.providers.push import PushProvider
from delivery_worker.providers.sms import SMSProvider


def _make_notification(channel: str) -> Notification:
    return Notification(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        channel=channel,
        priority=Priority.NORMAL,
        status=NotificationStatus.PENDING,
        source_event_id=uuid.uuid4(),
        source_event_type="user.registered",
        content={"subject": "Test", "body": "Hello"},
    )


class TestEmailProvider:
    def test_send_returns_success(self) -> None:
        provider = EmailProvider()
        result = provider.send(_make_notification(Channel.EMAIL))

        assert result.success is True
        assert "Email delivered" in result.details


class TestSMSProvider:
    def test_send_returns_success(self) -> None:
        provider = SMSProvider()
        result = provider.send(_make_notification(Channel.SMS))

        assert result.success is True
        assert "SMS delivered" in result.details


class TestPushProvider:
    def test_send_returns_success(self) -> None:
        provider = PushProvider()
        result = provider.send(_make_notification(Channel.PUSH))

        assert result.success is True
        assert "Push delivered" in result.details


class TestProviderRegistry:
    def test_get_returns_registered_provider(self) -> None:
        registry = ProviderRegistry()
        provider = EmailProvider()
        registry.register(Channel.EMAIL, provider)

        assert registry.get(Channel.EMAIL) is provider

    def test_get_raises_for_unknown_channel(self) -> None:
        registry = ProviderRegistry()

        with pytest.raises(KeyError):
            registry.get("unknown")

    def test_default_registry_has_all_channels(self) -> None:
        registry = create_default_registry()

        assert isinstance(registry.get(Channel.EMAIL), EmailProvider)
        assert isinstance(registry.get(Channel.SMS), SMSProvider)
        assert isinstance(registry.get(Channel.PUSH), PushProvider)
