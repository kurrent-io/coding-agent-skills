/**
 * KurrentDB Node.js Client Example - Persistent Subscriptions with all NACK actions
 */

import {
    KurrentDBClient,
    jsonEvent,
    persistentSubscriptionToStreamSettingsFromDefaults,
    PARK,
    RETRY,
    SKIP,
    STOP,
} from "@kurrent/kurrentdb-client";
import { v4 as uuid } from "uuid";

// === NACK ACTIONS ===
// Available NACK actions for persistent subscriptions:
// - PARK  : Move to parked queue for manual inspection
// - RETRY : Retry processing immediately
// - SKIP  : Skip this event and continue
// - STOP  : Stop the subscription

// === CONNECTION ===
const client = KurrentDBClient.connectionString`kurrentdb://admin:changeit@localhost:2113?tls=false`;
console.log("Connected to KurrentDB");

const streamName = "orders";
const groupName = "order-processor";

// === CREATE PERSISTENT SUBSCRIPTION ===
try {
    await client.createPersistentSubscriptionToStream(
        streamName,
        groupName,
        persistentSubscriptionToStreamSettingsFromDefaults()
    );
    console.log(`Created persistent subscription '${groupName}' on stream '${streamName}'`);
} catch (error) {
    if (error.message?.includes("already exists")) {
        console.log(`Persistent subscription '${groupName}' already exists`);
    } else {
        throw error;
    }
}

// === APPEND SOME TEST EVENTS ===
for (let i = 0; i < 3; i++) {
    const event = jsonEvent({
        type: "OrderCreated",
        data: {
            orderId: uuid(),
            amount: 10.0 * (i + 1),
        },
    });
    await client.appendToStream(streamName, event);
    console.log(`Appended OrderCreated event #${i + 1}`);
}

// === SUBSCRIBE TO PERSISTENT SUBSCRIPTION ===
console.log("\nSubscribing to persistent subscription...");

const subscription = client.subscribeToPersistentSubscriptionToStream(
    streamName,
    groupName
);

let count = 0;
try {
    for await (const event of subscription) {
        try {
            console.log(`  Processing: ${event.event?.type} (retry: ${event.retryCount})`);
            console.log(`  Data: ${JSON.stringify(event.event?.data)}`);

            // Simulate processing with different outcomes based on amount
            const amount = event.event?.data?.amount || 0;

            if (amount > 25) {
                // Simulate transient failure - retry immediately
                await subscription.nack(RETRY, "Transient failure - retrying", event);
                console.log(`  Retrying event (transient failure)`);
            } else if (amount > 20) {
                // Simulate permanent failure - park for inspection
                await subscription.nack(PARK, "Permanent failure - parking", event);
                console.log(`  Parked event (permanent failure)`);
            } else if (amount > 15) {
                // Skip malformed/invalid event
                await subscription.nack(SKIP, "Invalid data - skipping", event);
                console.log(`  Skipped event (invalid data)`);
            } else {
                // Success - acknowledge
                await subscription.ack(event);
                console.log(`  Acknowledged event`);
            }
        } catch (error) {
            // Park failed event for later inspection
            await subscription.nack(PARK, error.toString(), event);
            console.log(`  Parked event due to error: ${error.message}`);
        }

        count++;
        if (count >= 3) {
            break;
        }
    }
} catch (error) {
    console.log(`Subscription was dropped: ${error}`);
}

// Note: STOP would stop the subscription entirely
// await subscription.nack(STOP, "Stopping subscription", event);

console.log("\nDone!");
process.exit(0);
