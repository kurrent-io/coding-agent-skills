#!/usr/bin/env python3
"""
KurrentDB Python In-Memory Projection Example
Demonstrates: Subscribe to events, build state, track checkpoint
"""

import json
import os
import sys
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional
from kurrentdbclient import KurrentDBClient, NewEvent, StreamState


def log(msg):
    print(msg)
    sys.stdout.flush()


# === MINIMAL PROJECTION FRAMEWORK ===
@dataclass
class Projection:
    name: str
    state: Dict[str, Any] = field(default_factory=dict)
    checkpoint: Optional[int] = None
    _handlers: Dict[str, Callable] = field(default_factory=dict)

    def on(self, event_type: str, handler: Callable) -> "Projection":
        self._handlers[event_type] = handler
        return self

    def get(self, stream_id: str) -> Optional[Any]:
        return self.state.get(stream_id)

    def get_all(self) -> Dict[str, Any]:
        return self.state.copy()

    def apply(self, event) -> bool:
        handler = self._handlers.get(event.type)
        if handler:
            stream_id = event.stream_name
            current = self.state.get(stream_id, {})
            data = json.loads(event.data.decode()) if event.data else {}
            self.state[stream_id] = handler(current, data, event)
            self.checkpoint = event.commit_position
            return True
        return False


# === SETUP ===
connection_string = os.environ.get(
    "KURRENTDB_CONNECTION_STRING",
    "kurrentdb://localhost:2113?tls=false"
)
client = KurrentDBClient(uri=connection_string)
log(f"Connected to KurrentDB at {connection_string}")


# === DEFINE PROJECTION ===
def handle_order_created(state, data, event):
    return {
        "order_id": data.get("orderId"),
        "customer_id": data.get("customerId"),
        "amount": data.get("amount"),
        "status": "created",
        "items": []
    }


def handle_item_added(state, data, event):
    return {
        **state,
        "items": state.get("items", []) + [data.get("item")],
        "amount": state.get("amount", 0) + data.get("price", 0)
    }


def handle_order_shipped(state, data, event):
    return {
        **state,
        "status": "shipped",
        "shipped_at": data.get("shippedAt")
    }


def handle_order_completed(state, data, event):
    return {
        **state,
        "status": "completed"
    }


order_projection = Projection("OrderSummary")
order_projection.on("OrderCreated", handle_order_created)
order_projection.on("ItemAdded", handle_item_added)
order_projection.on("OrderShipped", handle_order_shipped)
order_projection.on("OrderCompleted", handle_order_completed)


# === TEST: Append test events ===
log("\n=== Appending test events ===")

order_id_1 = str(uuid.uuid4())
order_id_2 = str(uuid.uuid4())
stream_1 = f"order-{order_id_1}"
stream_2 = f"order-{order_id_2}"


def make_event(event_type: str, data: dict) -> NewEvent:
    return NewEvent(
        type=event_type,
        data=json.dumps(data).encode("utf-8"),
        content_type="application/json"
    )


# Order 1: Created -> ItemAdded -> Shipped -> Completed
client.append_to_stream(
    stream_name=stream_1,
    current_version=StreamState.ANY,
    events=[make_event("OrderCreated", {"orderId": order_id_1, "customerId": "cust-1", "amount": 100})]
)
client.append_to_stream(
    stream_name=stream_1,
    current_version=StreamState.ANY,
    events=[make_event("ItemAdded", {"item": "Widget", "price": 25})]
)
client.append_to_stream(
    stream_name=stream_1,
    current_version=StreamState.ANY,
    events=[make_event("OrderShipped", {"shippedAt": "2024-01-15T10:00:00Z"})]
)
client.append_to_stream(
    stream_name=stream_1,
    current_version=StreamState.ANY,
    events=[make_event("OrderCompleted", {})]
)

# Order 2: Created -> ItemAdded (still pending)
client.append_to_stream(
    stream_name=stream_2,
    current_version=StreamState.ANY,
    events=[make_event("OrderCreated", {"orderId": order_id_2, "customerId": "cust-2", "amount": 50})]
)
client.append_to_stream(
    stream_name=stream_2,
    current_version=StreamState.ANY,
    events=[make_event("ItemAdded", {"item": "Gadget", "price": 30})]
)

log(f"Created order streams: {stream_1}, {stream_2}")


# === RUN PROJECTION ===
log("\n=== Running projection ===")

subscription = client.subscribe_to_all(commit_position=0)

target_streams = {stream_1, stream_2}
target_events_count = {stream_1: 0, stream_2: 0}
expected_counts = {stream_1: 4, stream_2: 2}  # Order 1: 4 events, Order 2: 2 events

for event in subscription:
    # Skip system streams
    if event.stream_name.startswith("$"):
        continue

    if order_projection.apply(event):
        log(f"  Processed: {event.type} on {event.stream_name}")

        if event.stream_name in target_streams:
            target_events_count[event.stream_name] += 1

    # Stop when we've processed all our test events
    if (target_events_count[stream_1] >= expected_counts[stream_1] and
        target_events_count[stream_2] >= expected_counts[stream_2]):
        break

    # Safety limit
    total_processed = sum(target_events_count.values())
    if total_processed > 200:
        break


# === VERIFY RESULTS ===
log("\n=== Projection Results ===")

order1_state = order_projection.get(stream_1)
order2_state = order_projection.get(stream_2)

log(f"\nOrder 1 ({stream_1}):")
log(json.dumps(order1_state, indent=2))

log(f"\nOrder 2 ({stream_2}):")
log(json.dumps(order2_state, indent=2))


# === ASSERTIONS ===
log("\n=== Running assertions ===")

passed = True

# Order 1 assertions
if order1_state.get("status") != "completed":
    log(f"FAIL: Order 1 status should be 'completed', got '{order1_state.get('status')}'")
    passed = False

if order1_state.get("amount") != 125:
    log(f"FAIL: Order 1 amount should be 125, got {order1_state.get('amount')}")
    passed = False

if len(order1_state.get("items", [])) != 1:
    log(f"FAIL: Order 1 should have 1 item, got {len(order1_state.get('items', []))}")
    passed = False

# Order 2 assertions
if order2_state.get("status") != "created":
    log(f"FAIL: Order 2 status should be 'created', got '{order2_state.get('status')}'")
    passed = False

if order2_state.get("amount") != 80:
    log(f"FAIL: Order 2 amount should be 80, got {order2_state.get('amount')}")
    passed = False

# Checkpoint assertion
if order_projection.checkpoint is None:
    log("FAIL: Checkpoint should be set")
    passed = False

if passed:
    log("\nAll projection tests passed!")
else:
    log("\nSome tests failed!")
    sys.exit(1)

client.close()
