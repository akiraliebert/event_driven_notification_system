"""Re-export KafkaStatusPublisher from shared for backwards compatibility."""

from shared.kafka import KafkaStatusPublisher

__all__ = ["KafkaStatusPublisher"]
