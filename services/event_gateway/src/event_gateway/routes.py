import logging
from typing import Any

from flask import Blueprint, Response, current_app, jsonify, request
from pydantic import ValidationError

from shared.enums import ALL_EVENT_TYPES
from shared.events.typed import parse_event

from event_gateway.producer import KafkaEventProducer

logger = logging.getLogger(__name__)

bp = Blueprint("gateway", __name__)


def _error(message: str, status: int, **extra: Any) -> tuple[Response, int]:
    body: dict[str, Any] = {"error": message}
    body.update(extra)
    return jsonify(body), status


@bp.post("/events")
def post_event() -> tuple[Response, int]:
    body = request.get_json(silent=True)
    if body is None:
        return _error("Request body must be valid JSON", 400)

    event_type = body.get("event_type")
    payload = body.get("payload")

    if event_type is None or payload is None:
        return _error("Both 'event_type' and 'payload' are required", 400)

    if not isinstance(payload, dict):
        return _error("'payload' must be a JSON object", 400)

    if event_type not in ALL_EVENT_TYPES:
        return _error(
            "Unknown event type",
            422,
            event_type=event_type,
            supported=sorted(ALL_EVENT_TYPES),
        )

    raw_event = {
        "metadata": {"event_type": event_type},
        "payload": payload,
    }

    try:
        event = parse_event(raw_event)
    except ValidationError as exc:
        return _error(
            "Payload validation failed",
            400,
            details=exc.errors(include_url=False),
        )

    partition_key = event.payload.user_id

    producer: KafkaEventProducer = current_app.extensions["kafka_producer"]
    try:
        producer.publish_event(event, partition_key=partition_key)
    except Exception:
        logger.exception("Failed to publish event to Kafka")
        return _error("Event broker unavailable", 503)

    event_id = str(event.metadata.event_id)
    logger.info(
        "Event published",
        extra={
            "event_id": event_id,
            "event_type": event_type,
            "user_id": str(partition_key),
        },
    )

    return jsonify({"status": "accepted", "event_id": event_id}), 202


@bp.get("/health")
def health() -> tuple[Response, int]:
    producer: KafkaEventProducer = current_app.extensions["kafka_producer"]
    kafka_ok = producer.health_check()

    status = "healthy" if kafka_ok else "unhealthy"
    code = 200 if kafka_ok else 503

    return jsonify({
        "status": status,
        "checks": {"kafka": "ok" if kafka_ok else "unreachable"},
    }), code
