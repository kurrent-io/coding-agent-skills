#!/usr/bin/env python3
"""KurrentDB Python Client Example - Persistent Subscriptions"""

import json
import uuid
from kurrentdbclient import KurrentDBClient, NewEvent, StreamState

# === CONNECTION ===
client = KurrentDBClient(uri="kurrentdb://admin:changeit@localhost:2113?tls=false")
print("Connected to KurrentDB")

stream_name = "orders"
group_name = "order-processor"

# === CREATE PERSISTENT SUBSCRIPTION ===
try:
    client.create_subscription_to_stream(
        group_name=group_name,
        stream_name=stream_name
    )
    print(f"Created persistent subscription '{group_name}' on stream '{stream_name}'")
except Exception as e:
    if "already exists" in str(e).lower():
        print(f"Persistent subscription '{group_name}' already exists")
    else:
        raise

# === APPEND SOME TEST EVENTS ===
for i in range(3):
    event = NewEvent(
        type="OrderCreated",
        data=json.dumps({
            "order_id": str(uuid.uuid4()),
            "amount": 10.00 * (i + 1)
        }).encode("utf-8"),
        content_type="application/json"
    )
    client.append_to_stream(
        stream_name=stream_name,
        current_version=StreamState.ANY,
        events=[event]
    )
    print(f"Appended OrderCreated event #{i + 1}")

# === SUBSCRIBE TO PERSISTENT SUBSCRIPTION ===
print("\nSubscribing to persistent subscription...")

subscription = client.read_subscription_to_stream(
    group_name=group_name,
    stream_name=stream_name
)

count = 0
for event in subscription:
    try:
        print(f"  Processing: {event.type}")
        print(f"  Data: {event.data.decode('utf-8')}")

        # Simulate processing
        # ... your business logic here ...

        # Acknowledge success
        subscription.ack(event.ack_id)
        print(f"  Acknowledged event")

    except Exception as e:
        # Park failed event for later inspection
        subscription.nack(event.ack_id, action="park")
        print(f"  Parked event: {e}")

    count += 1
    if count >= 3:
        break

print("\nDone!")
