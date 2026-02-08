import atexit
import logging

from flask import Flask

from event_gateway.log import setup_logging
from event_gateway.producer import KafkaEventProducer
from event_gateway.routes import bp

logger = logging.getLogger(__name__)


def create_app(producer: KafkaEventProducer) -> Flask:
    """Flask application factory.

    Args:
        producer: Kafka producer instance (real or mock for tests).
    """
    setup_logging()

    app = Flask(__name__)
    app.extensions["kafka_producer"] = producer

    app.register_blueprint(bp)

    atexit.register(producer.close)

    logger.info("Event Gateway initialized")
    return app
