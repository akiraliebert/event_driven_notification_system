"""WSGI entry point for gunicorn.

Usage:
    gunicorn event_gateway.wsgi:app --bind 0.0.0.0:8000
"""
from shared.config import KafkaConfig

from event_gateway.app import create_app
from event_gateway.producer import KafkaEventProducer

_producer = KafkaEventProducer(KafkaConfig())
app = create_app(_producer)
