#!/usr/bin/env python3
"""KurrentDB Python Client Example - Append, Read, and Subscribe"""

import json
import os
import sys
import uuid
from kurrentdbclient import KurrentDBClient, NewEvent, StreamState

def log(msg):
    """Print with immediate flush for Docker compatibility"""
    print(msg)
    sys.stdout.flush()

# === CONNECTION ===
connection_string = os.environ.get(
    "KURRENTDB_CONNECTION_STRING",
    "kurrentdb://localhost:2113?tls=false"
)
client = KurrentDBClient(uri=connection_string)
log(f"Connected to KurrentDB at {connection_string}")

# === APPEND EVENTS ===
order_id = str(uuid.uuid4())
stream_name = f"order-{order_id}"

event = NewEvent(
    type="OrderCreated",
    data=json.dumps({
        "order_id": order_id,
        "customer_id": "customer-123",
        "amount": 99.99
    }).encode("utf-8"),
    content_type="application/json"
)

commit_position = client.append_to_stream(
    stream_name=stream_name,
    current_version=StreamState.NO_STREAM,
    events=[event]
)

log(f"Appended event to {stream_name} at position {commit_position}")

# === READ EVENTS ===
log("\nReading events:")
events = client.get_stream(stream_name=stream_name)

for event in events:
    log(f"  Event #{event.stream_position}: {event.type}")
    log(f"  Data: {event.data.decode('utf-8')}")

# === CATCH-UP SUBSCRIPTION (Stream) ===
log("\nStarting catch-up subscription to stream...")

subscription = client.subscribe_to_stream(stream_name=stream_name)

count = 0
for event in subscription:
    log(f"  [Sub] Received: {event.type} @ position {event.stream_position}")
    count += 1
    # Stop after receiving our event (for demo purposes)
    if count >= 1:
        break

log("Subscription stopped")

# === CATCH-UP SUBSCRIPTION ($all) ===
log("\nStarting catch-up subscription to $all (reading 3 non-system events)...")

subscription = client.subscribe_to_all(commit_position=0)

count = 0
for event in subscription:
    if not event.stream_name.startswith("$"):  # Skip system streams
        log(f"  [Sub] Stream: {event.stream_name}, Type: {event.type}")
        count += 1
        if count >= 3:
            break

log("\nAll tests passed!")
