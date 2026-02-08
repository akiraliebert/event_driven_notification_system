"""Provider registry for channel-based delivery dispatch."""

from shared.enums import Channel

from delivery_worker.providers.base import DeliveryProvider
from delivery_worker.providers.email import EmailProvider
from delivery_worker.providers.push import PushProvider
from delivery_worker.providers.sms import SMSProvider


class ProviderRegistry:
    """Maps channel names to delivery provider instances."""

    def __init__(self) -> None:
        self._providers: dict[str, DeliveryProvider] = {}

    def register(self, channel: str, provider: DeliveryProvider) -> None:
        self._providers[channel] = provider

    def get(self, channel: str) -> DeliveryProvider:
        """Return the provider for a channel.

        Raises KeyError if no provider is registered for the channel.
        """
        return self._providers[channel]


def create_default_registry() -> ProviderRegistry:
    """Create a registry with all built-in providers."""
    registry = ProviderRegistry()
    registry.register(Channel.EMAIL, EmailProvider())
    registry.register(Channel.SMS, SMSProvider())
    registry.register(Channel.PUSH, PushProvider())
    return registry
