/**
 * KurrentDB Node.js In-Memory Projection Example
 * Demonstrates: Subscribe to events, build state, track checkpoint
 */

import {
    KurrentDBClient,
    jsonEvent,
    START,
    excludeSystemEvents,
} from "@kurrent/kurrentdb-client";
import { v4 as uuid } from "uuid";

// === MINIMAL PROJECTION FRAMEWORK ===
class Projection {
    constructor(name) {
        this.name = name;
        this.state = new Map();
        this.checkpoint = null;
        this.handlers = new Map();
    }

    on(eventType, handler) {
        this.handlers.set(eventType, handler);
        return this;
    }

    get(id) {
        return this.state.get(id);
    }

    getAll() {
        return Object.fromEntries(this.state);
    }

    apply(resolvedEvent) {
        const event = resolvedEvent.event;
        if (!event) return false;

        const handler = this.handlers.get(event.type);
        if (handler) {
            const streamId = event.streamId;
            const current = this.state.get(streamId) || {};
            const newState = handler(current, event.data, event);
            this.state.set(streamId, newState);
            this.checkpoint = resolvedEvent.commitPosition;
            return true;
        }
        return false;
    }
}

// === SETUP ===
const connectionString = process.env.KURRENTDB_CONNECTION_STRING || "kurrentdb://localhost:2113?tls=false";
const client = KurrentDBClient.connectionString(connectionString);
console.log(`Connected to KurrentDB at ${connectionString}`);

// === DEFINE PROJECTION ===
const orderProjection = new Projection("OrderSummary")
    .on("OrderCreated", (state, data) => ({
        orderId: data.orderId,
        customerId: data.customerId,
        amount: data.amount,
        status: "created",
        items: []
    }))
    .on("ItemAdded", (state, data) => ({
        ...state,
        items: [...(state.items || []), data.item],
        amount: state.amount + data.price
    }))
    .on("OrderShipped", (state, data) => ({
        ...state,
        status: "shipped",
        shippedAt: data.shippedAt
    }))
    .on("OrderCompleted", (state) => ({
        ...state,
        status: "completed"
    }));

// === TEST: Append test events ===
console.log("\n=== Appending test events ===");

const orderId1 = uuid();
const orderId2 = uuid();
const stream1 = `order-${orderId1}`;
const stream2 = `order-${orderId2}`;

// Order 1: Created -> ItemAdded -> Shipped -> Completed
await client.appendToStream(stream1, [
    jsonEvent({ type: "OrderCreated", data: { orderId: orderId1, customerId: "cust-1", amount: 100 } }),
]);
await client.appendToStream(stream1, [
    jsonEvent({ type: "ItemAdded", data: { item: "Widget", price: 25 } }),
]);
await client.appendToStream(stream1, [
    jsonEvent({ type: "OrderShipped", data: { shippedAt: new Date().toISOString() } }),
]);
await client.appendToStream(stream1, [
    jsonEvent({ type: "OrderCompleted", data: {} }),
]);

// Order 2: Created -> ItemAdded (still pending)
await client.appendToStream(stream2, [
    jsonEvent({ type: "OrderCreated", data: { orderId: orderId2, customerId: "cust-2", amount: 50 } }),
]);
await client.appendToStream(stream2, [
    jsonEvent({ type: "ItemAdded", data: { item: "Gadget", price: 30 } }),
]);

console.log(`Created order streams: ${stream1}, ${stream2}`);

// === RUN PROJECTION ===
console.log("\n=== Running projection ===");

const subscription = client.subscribeToAll({
    fromPosition: START,
    filter: excludeSystemEvents(),
});

const targetStreams = new Set([stream1, stream2]);
const targetEventsCount = { [stream1]: 0, [stream2]: 0 };
const expectedCounts = { [stream1]: 4, [stream2]: 2 }; // Order 1: 4 events, Order 2: 2 events

for await (const event of subscription) {
    const streamId = event.event?.streamId;

    if (orderProjection.apply(event)) {
        console.log(`  Processed: ${event.event.type} on ${streamId}`);

        if (targetStreams.has(streamId)) {
            targetEventsCount[streamId]++;
        }
    }

    // Stop when we've processed all our test events
    if (targetEventsCount[stream1] >= expectedCounts[stream1] &&
        targetEventsCount[stream2] >= expectedCounts[stream2]) {
        break;
    }

    // Safety limit
    const total = targetEventsCount[stream1] + targetEventsCount[stream2];
    if (total > 200) break;
}

// === VERIFY RESULTS ===
console.log("\n=== Projection Results ===");

const order1State = orderProjection.get(stream1);
const order2State = orderProjection.get(stream2);

console.log(`\nOrder 1 (${stream1}):`);
console.log(JSON.stringify(order1State, null, 2));

console.log(`\nOrder 2 (${stream2}):`);
console.log(JSON.stringify(order2State, null, 2));

// === ASSERTIONS ===
console.log("\n=== Running assertions ===");

let passed = true;

// Order 1 assertions
if (order1State?.status !== "completed") {
    console.error(`FAIL: Order 1 status should be 'completed', got '${order1State?.status}'`);
    passed = false;
}
if (order1State?.amount !== 125) {
    console.error(`FAIL: Order 1 amount should be 125, got ${order1State?.amount}`);
    passed = false;
}
if (order1State?.items?.length !== 1) {
    console.error(`FAIL: Order 1 should have 1 item, got ${order1State?.items?.length}`);
    passed = false;
}

// Order 2 assertions
if (order2State?.status !== "created") {
    console.error(`FAIL: Order 2 status should be 'created', got '${order2State?.status}'`);
    passed = false;
}
if (order2State?.amount !== 80) {
    console.error(`FAIL: Order 2 amount should be 80, got ${order2State?.amount}`);
    passed = false;
}

// Checkpoint assertion
if (!orderProjection.checkpoint) {
    console.error("FAIL: Checkpoint should be set");
    passed = false;
}

if (passed) {
    console.log("\nAll projection tests passed!");
} else {
    console.error("\nSome tests failed!");
    process.exit(1);
}

process.exit(0);
