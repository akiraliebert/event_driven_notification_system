"""Polling utilities for integration tests."""

import time
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from shared.db.models import Notification


def poll_notifications(
    session_factory: sessionmaker[Session],
    event_id: str | uuid.UUID,
    expected: int,
    timeout: float = 10.0,
    interval: float = 0.3,
) -> list[Notification]:
    """Poll DB until *expected* notifications appear for *event_id*.

    Returns whatever was found when the deadline is reached (the calling
    test will fail on its own assertion if the count is wrong).
    """
    deadline = time.monotonic() + timeout
    event_uuid = uuid.UUID(event_id) if isinstance(event_id, str) else event_id

    while True:
        with session_factory() as session:
            stmt = select(Notification).where(
                Notification.source_event_id == event_uuid,
            )
            notifications = list(session.scalars(stmt).all())
            if len(notifications) >= expected:
                for n in notifications:
                    session.expunge(n)
                return notifications

        if time.monotonic() >= deadline:
            break
        time.sleep(interval)

    # Return partial result — test assertion will report the mismatch
    with session_factory() as session:
        stmt = select(Notification).where(
            Notification.source_event_id == event_uuid,
        )
        notifications = list(session.scalars(stmt).all())
        for n in notifications:
            session.expunge(n)
        return notifications


def poll_notifications_by_user(
    session_factory: sessionmaker[Session],
    user_id: str | uuid.UUID,
    expected: int,
    timeout: float = 15.0,
    interval: float = 0.3,
) -> list[Notification]:
    """Poll DB until *expected* notifications appear for *user_id*."""
    deadline = time.monotonic() + timeout
    uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id

    while True:
        with session_factory() as session:
            stmt = select(Notification).where(Notification.user_id == uid)
            notifications = list(session.scalars(stmt).all())
            if len(notifications) >= expected:
                for n in notifications:
                    session.expunge(n)
                return notifications

        if time.monotonic() >= deadline:
            break
        time.sleep(interval)

    with session_factory() as session:
        stmt = select(Notification).where(Notification.user_id == uid)
        notifications = list(session.scalars(stmt).all())
        for n in notifications:
            session.expunge(n)
        return notifications
