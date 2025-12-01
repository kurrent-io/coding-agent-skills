#!/usr/bin/env python3
"""KurrentDB Python Client Example - Persistent Subscriptions with all NACK actions"""

import json
import uuid
from kurrentdbclient import KurrentDBClient, NewEvent, StreamState

# === CONNECTION ===
client = KurrentDBClient(uri="kurrentdb://admin:changeit@localhost:2113?tls=false")
print("Connected to KurrentDB")

stream_name = "orders"
group_name = "order-processor"

# === NACK ACTIONS ===
# Available NACK actions for persistent subscriptions:
# - "park"  : Move to parked queue for manual inspection
# - "retry" : Retry processing immediately
# - "skip"  : Skip this event and continue
# - "stop"  : Stop the subscription

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

        # Simulate processing with different outcomes
        data = json.loads(event.data.decode('utf-8'))
        amount = data.get("amount", 0)

        if amount > 25:
            # Simulate transient failure - retry immediately
            subscription.nack(event.ack_id, action="retry")
            print(f"  Retrying event (transient failure)")
        elif amount > 20:
            # Simulate permanent failure - park for inspection
            subscription.nack(event.ack_id, action="park")
            print(f"  Parked event (permanent failure)")
        elif amount > 15:
            # Skip malformed/invalid event
            subscription.nack(event.ack_id, action="skip")
            print(f"  Skipped event (invalid data)")
        else:
            # Success - acknowledge
            subscription.ack(event.ack_id)
            print(f"  Acknowledged event")

    except Exception as e:
        # Park failed event for later inspection
        subscription.nack(event.ack_id, action="park")
        print(f"  Parked event due to error: {e}")

    count += 1
    if count >= 3:
        break

# Note: action="stop" would stop the subscription entirely
# subscription.nack(event.ack_id, action="stop")

print("\nDone!")
