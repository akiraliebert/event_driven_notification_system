#!/usr/bin/env python3
"""Demo: send all event types through the notification system.

Requires the full stack to be running:
    make up-app

Usage:
    python scripts/demo.py [--gateway-url URL]
"""

import argparse
import sys
import uuid

import httpx

EVENTS = [
    {
        "event_type": "user.registered",
        "payload": {
            "user_id": str(uuid.uuid4()),
            "email": "alice@example.com",
        },
    },
    {
        "event_type": "order.completed",
        "payload": {
            "user_id": str(uuid.uuid4()),
            "order_id": str(uuid.uuid4()),
            "total_amount": "149.99",
        },
    },
    {
        "event_type": "payment.failed",
        "payload": {
            "user_id": str(uuid.uuid4()),
            "payment_id": str(uuid.uuid4()),
            "reason": "Insufficient funds",
        },
    },
]


def main() -> None:
    parser = argparse.ArgumentParser(description="Send demo events")
    parser.add_argument(
        "--gateway-url",
        default="http://localhost:8000",
        help="Event Gateway base URL (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    with httpx.Client(base_url=args.gateway_url, timeout=10.0) as client:
        # Health check
        try:
            resp = client.get("/health")
        except httpx.ConnectError:
            print(f"Cannot connect to {args.gateway_url}")
            print("Make sure services are running: make up-app")
            sys.exit(1)

        if resp.status_code != 200:
            print(f"Gateway unhealthy: {resp.text}")
            sys.exit(1)

        print(f"Gateway healthy at {args.gateway_url}\n")

        # Send events
        for event in EVENTS:
            resp = client.post("/events", json=event)
            status = resp.status_code
            body = resp.json()

            if status == 202:
                event_id = body["event_id"]
                print(f"  {event['event_type']:20s}  -> accepted  event_id={event_id}")
            else:
                print(f"  {event['event_type']:20s}  -> ERROR {status}: {body}")

    print(f"\nSent {len(EVENTS)} events.")
    print("\nVerify results:")
    print("  make logs SVC=notification-service")
    print("  make logs SVC=delivery-worker")
    print("  make psql")
    print("    SELECT source_event_type, channel, priority, status")
    print("      FROM notifications ORDER BY created_at;")


if __name__ == "__main__":
    main()
