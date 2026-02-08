import json
from unittest.mock import MagicMock
from uuid import UUID, uuid4

from confluent_kafka import KafkaException
from flask.testing import FlaskClient


class TestPostEvents:
    """POST /events endpoint."""

    def test_user_registered_returns_202(
        self, client: FlaskClient, mock_producer: MagicMock
    ) -> None:
        resp = client.post("/events", json={
            "event_type": "user.registered",
            "payload": {"user_id": str(uuid4()), "email": "test@example.com"},
        })

        assert resp.status_code == 202
        data = resp.get_json()
        assert data["status"] == "accepted"
        UUID(data["event_id"])
        mock_producer.publish_event.assert_called_once()

    def test_order_completed_returns_202(
        self, client: FlaskClient, mock_producer: MagicMock
    ) -> None:
        resp = client.post("/events", json={
            "event_type": "order.completed",
            "payload": {
                "order_id": str(uuid4()),
                "user_id": str(uuid4()),
                "total_amount": "99.99",
            },
        })

        assert resp.status_code == 202
        mock_producer.publish_event.assert_called_once()

    def test_payment_failed_returns_202(
        self, client: FlaskClient, mock_producer: MagicMock
    ) -> None:
        resp = client.post("/events", json={
            "event_type": "payment.failed",
            "payload": {
                "payment_id": str(uuid4()),
                "user_id": str(uuid4()),
                "reason": "insufficient funds",
            },
        })

        assert resp.status_code == 202
        mock_producer.publish_event.assert_called_once()

    def test_no_json_body_returns_400(self, client: FlaskClient) -> None:
        resp = client.post(
            "/events", data="not json", content_type="text/plain"
        )

        assert resp.status_code == 400
        assert "JSON" in resp.get_json()["error"]

    def test_missing_event_type_returns_400(self, client: FlaskClient) -> None:
        resp = client.post("/events", json={"payload": {}})

        assert resp.status_code == 400
        assert "required" in resp.get_json()["error"]

    def test_missing_payload_returns_400(self, client: FlaskClient) -> None:
        resp = client.post("/events", json={"event_type": "user.registered"})

        assert resp.status_code == 400
        assert "required" in resp.get_json()["error"]

    def test_payload_not_object_returns_400(self, client: FlaskClient) -> None:
        resp = client.post("/events", json={
            "event_type": "user.registered",
            "payload": "not a dict",
        })

        assert resp.status_code == 400
        assert "object" in resp.get_json()["error"]

    def test_unknown_event_type_returns_422(self, client: FlaskClient) -> None:
        resp = client.post("/events", json={
            "event_type": "unknown.event",
            "payload": {},
        })

        assert resp.status_code == 422
        data = resp.get_json()
        assert "Unknown event type" in data["error"]
        assert "supported" in data

    def test_invalid_email_returns_400(self, client: FlaskClient) -> None:
        resp = client.post("/events", json={
            "event_type": "user.registered",
            "payload": {"user_id": str(uuid4()), "email": "not-an-email"},
        })

        assert resp.status_code == 400
        assert "details" in resp.get_json()

    def test_missing_payload_field_returns_400(
        self, client: FlaskClient
    ) -> None:
        resp = client.post("/events", json={
            "event_type": "user.registered",
            "payload": {"user_id": str(uuid4())},
        })

        assert resp.status_code == 400
        assert "details" in resp.get_json()

    def test_kafka_failure_returns_503(
        self, client: FlaskClient, mock_producer: MagicMock
    ) -> None:
        mock_producer.publish_event.side_effect = KafkaException(
            KafkaException(None)
        )

        resp = client.post("/events", json={
            "event_type": "user.registered",
            "payload": {"user_id": str(uuid4()), "email": "a@b.com"},
        })

        assert resp.status_code == 503
        assert "unavailable" in resp.get_json()["error"]

    def test_partition_key_is_user_id(
        self, client: FlaskClient, mock_producer: MagicMock
    ) -> None:
        user_id = uuid4()

        client.post("/events", json={
            "event_type": "user.registered",
            "payload": {"user_id": str(user_id), "email": "a@b.com"},
        })

        call_args = mock_producer.publish_event.call_args
        assert call_args.kwargs["partition_key"] == user_id

    def test_event_id_is_generated(self, client: FlaskClient) -> None:
        resp = client.post("/events", json={
            "event_type": "user.registered",
            "payload": {"user_id": str(uuid4()), "email": "a@b.com"},
        })

        event_id = resp.get_json()["event_id"]
        UUID(event_id)


class TestHealth:
    """GET /health endpoint."""

    def test_healthy_returns_200(
        self, client: FlaskClient, mock_producer: MagicMock
    ) -> None:
        mock_producer.health_check.return_value = True

        resp = client.get("/health")

        assert resp.status_code == 200
        data = resp.get_json()
        assert data["status"] == "healthy"
        assert data["checks"]["kafka"] == "ok"

    def test_unhealthy_returns_503(
        self, client: FlaskClient, mock_producer: MagicMock
    ) -> None:
        mock_producer.health_check.return_value = False

        resp = client.get("/health")

        assert resp.status_code == 503
        data = resp.get_json()
        assert data["status"] == "unhealthy"
        assert data["checks"]["kafka"] == "unreachable"
