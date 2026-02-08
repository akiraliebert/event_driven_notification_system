"""Dev entry point: python -m event_gateway."""
from shared.config import KafkaConfig

from event_gateway.app import create_app
from event_gateway.config import GatewayConfig
from event_gateway.producer import KafkaEventProducer


def main() -> None:
    config = GatewayConfig()
    producer = KafkaEventProducer(KafkaConfig())
    app = create_app(producer)
    app.run(host=config.host, port=config.port)


if __name__ == "__main__":
    main()
