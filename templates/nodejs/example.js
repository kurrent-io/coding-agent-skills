/**
 * KurrentDB Node.js Client Example - Append, Read, and Subscribe
 */

import {
    KurrentDBClient,
    jsonEvent,
    FORWARDS,
    START,
    END,
} from "@kurrent/kurrentdb-client";
import { v4 as uuid } from "uuid";

// === CONNECTION ===
const connectionString = process.env.KURRENTDB_CONNECTION_STRING || "kurrentdb://localhost:2113?tls=false";
const client = KurrentDBClient.connectionString(connectionString);
console.log(`Connected to KurrentDB at ${connectionString}`);

// === APPEND EVENTS ===
const orderId = uuid();
const streamName = `order-${orderId}`;

const event = jsonEvent({
    type: "OrderCreated",
    data: {
        orderId,
        customerId: "customer-123",
        amount: 99.99,
    },
});

const writeResult = await client.appendToStream(streamName, event);
console.log(`Appended event to ${streamName} at revision ${writeResult.nextExpectedRevision}`);

// === READ EVENTS ===
console.log("\nReading events:");
const events = client.readStream(streamName, {
    direction: FORWARDS,
    fromRevision: START,
    maxCount: 100,
});

for await (const resolvedEvent of events) {
    console.log(`  Event #${resolvedEvent.event?.revision}: ${resolvedEvent.event?.type}`);
    console.log(`  Data: ${JSON.stringify(resolvedEvent.event?.data)}`);
}

// === CATCH-UP SUBSCRIPTION (Stream) ===
console.log("\nStarting catch-up subscription to stream...");

const streamSubscription = client.subscribeToStream(streamName, {
    fromRevision: START,
});

let count = 0;
for await (const resolvedEvent of streamSubscription) {
    console.log(`  [Sub] Received: ${resolvedEvent.event?.type} @ revision ${resolvedEvent.event?.revision}`);
    count++;
    // Stop after receiving our event (for demo purposes)
    if (count >= 1) {
        break;
    }
}

console.log("Subscription stopped");

// === CATCH-UP SUBSCRIPTION ($all) ===
console.log("\nStarting catch-up subscription to $all (last 5 events)...");

const allSubscription = client.subscribeToAll({
    fromPosition: START,
});

count = 0;
for await (const resolvedEvent of allSubscription) {
    const eventStreamId = resolvedEvent.event?.streamId;
    if (eventStreamId && !eventStreamId.startsWith("$")) {
        console.log(`  [Sub] Stream: ${eventStreamId}, Type: ${resolvedEvent.event?.type}`);
        count++;
        if (count >= 5) {
            break;
        }
    }
}

console.log("\nAll tests passed!");
process.exit(0);
