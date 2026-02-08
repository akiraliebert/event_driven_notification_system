from unittest.mock import MagicMock

import pytest
from flask import Flask
from flask.testing import FlaskClient

from event_gateway.app import create_app
from event_gateway.producer import KafkaEventProducer


@pytest.fixture()
def mock_producer() -> MagicMock:
    producer = MagicMock(spec=KafkaEventProducer)
    producer.health_check.return_value = True
    return producer


@pytest.fixture()
def app(mock_producer: MagicMock) -> Flask:
    app = create_app(mock_producer)
    app.config["TESTING"] = True
    return app


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    return app.test_client()
