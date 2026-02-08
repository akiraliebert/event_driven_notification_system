"""User preferences integration tests.

Verifies that disabled channels are not sent notifications
and that completely disabled users receive nothing.
"""

import uuid

import httpx
import pytest
from sqlalchemy.orm import Session, sessionmaker

from shared.db.models import UserPreference
from shared.enums import Channel

from tests.integration.helpers import poll_notifications

pytestmark = pytest.mark.integration


class TestDisabledChannel:
    def test_email_disabled_only_sms_and_push_created(
        self,
        http_client: httpx.Client,
        notification_consumer: None,
        session_factory: sessionmaker[Session],
    ) -> None:
        user_id = uuid.uuid4()

        # Pre-create preference with email disabled
        with session_factory() as session:
            pref = UserPreference(
                user_id=user_id,
                channels=[Channel.SMS, Channel.PUSH],
                timezone="UTC",
            )
            session.add(pref)
            session.commit()

        resp = http_client.post("/events", json={
            "event_type": "user.registered",
            "payload": {"user_id": str(user_id), "email": "no-email@test.com"},
        })
        assert resp.status_code == 202
        event_id = resp.json()["event_id"]

        notifications = poll_notifications(session_factory, event_id, expected=2)
        assert len(notifications) == 2

        channels = {n.channel for n in notifications}
        assert channels == {"sms", "push"}


class TestAllChannelsDisabled:
    def test_no_notifications_created(
        self,
        http_client: httpx.Client,
        notification_consumer: None,
        session_factory: sessionmaker[Session],
    ) -> None:
        user_id = uuid.uuid4()

        # Pre-create preference with all channels disabled
        with session_factory() as session:
            pref = UserPreference(
                user_id=user_id,
                channels=[],
                timezone="UTC",
            )
            session.add(pref)
            session.commit()

        resp = http_client.post("/events", json={
            "event_type": "user.registered",
            "payload": {"user_id": str(user_id), "email": "none@test.com"},
        })
        assert resp.status_code == 202
        event_id = resp.json()["event_id"]

        # Give consumer time to process — should create nothing
        notifications = poll_notifications(
            session_factory, event_id, expected=1, timeout=3.0,
        )
        assert len(notifications) == 0
