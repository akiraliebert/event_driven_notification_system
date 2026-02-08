"""Re-export KafkaStatusPublisher from shared for backwards compatibility."""

from shared.kafka import KafkaStatusPublisher

# notification_service historically called this KafkaStatusProducer
KafkaStatusProducer = KafkaStatusPublisher

__all__ = ["KafkaStatusProducer", "KafkaStatusPublisher"]
