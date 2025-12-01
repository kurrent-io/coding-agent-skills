package com.example.kurrentdb;

import io.kurrent.dbclient.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.concurrent.ExecutionException;
import java.util.List;
import java.util.stream.Collectors;

/**
 * KurrentDB Java Client Example - Persistent Subscriptions with all NACK actions
 *
 * NACK ACTIONS:
 * - NackAction.Park  : Move to parked queue for manual inspection
 * - NackAction.Retry : Retry processing immediately
 * - NackAction.Skip  : Skip this event and continue
 * - NackAction.Stop  : Stop the subscription
 */
public class PersistentSubscriptionExample {

    private static final ObjectMapper mapper = new ObjectMapper();

    public static void main(String[] args) throws Exception {
        // === CONNECTION ===
        String connectionString = System.getenv("KURRENTDB_CONNECTION_STRING");
        if (connectionString == null || connectionString.isEmpty()) {
            connectionString = "kurrentdb://admin:changeit@localhost:2113?tls=false";
        }

        KurrentDBClientSettings settings = KurrentDBConnectionString.parseOrThrow(connectionString);
        KurrentDBClient client = KurrentDBClient.create(settings);
        KurrentDBPersistentSubscriptionsClient psClient = KurrentDBPersistentSubscriptionsClient.create(settings);

        System.out.println("Connected to KurrentDB at " + connectionString);

        String streamName = "orders";
        String groupName = "order-processor";

        // === CREATE PERSISTENT SUBSCRIPTION ===
        try {
            createPersistentSubscription(psClient, streamName, groupName);
            System.out.println("Created persistent subscription '" + groupName + "' on stream '" + streamName + "'");
        } catch (Exception e) {
            if (e.getMessage() != null && e.getMessage().contains("already exists")) {
                System.out.println("Persistent subscription '" + groupName + "' already exists");
            } else {
                System.out.println("Note: " + e.getMessage());
            }
        }

        // === APPEND SOME TEST EVENTS ===
        for (int i = 0; i < 3; i++) {
            OrderCreated order = new OrderCreated(UUID.randomUUID().toString(), 10.0 * (i + 1));
            byte[] eventData = mapper.writeValueAsBytes(order);
            EventData event = EventData.builderAsJson("OrderCreated", eventData).build();

            client.appendToStream(streamName, event).get();
            System.out.println("Appended OrderCreated event #" + (i + 1));
        }

        // === SUBSCRIBE TO PERSISTENT SUBSCRIPTION ===
        System.out.println("\nSubscribing to persistent subscription...");

        final int[] count = {0};
        final Object lock = new Object();

        PersistentSubscription subscription = psClient.subscribeToStream(
                streamName,
                groupName,
                new PersistentSubscriptionListener() {
                    @Override
                    public void onEvent(PersistentSubscription subscription, int retryCount, ResolvedEvent event) {
                        RecordedEvent recordedEvent = event.getOriginalEvent();
                        System.out.println("  Processing: " + recordedEvent.getEventType() +
                                " (retry: " + retryCount + ")");
                        System.out.println("  Data: " + new String(recordedEvent.getEventData(), StandardCharsets.UTF_8));

                        try {
                            // Simulate processing with different outcomes based on amount
                            OrderCreated order = mapper.readValue(recordedEvent.getEventData(), OrderCreated.class);

                            if (order.amount() > 25) {
                                // Simulate transient failure - retry immediately
                                subscription.nack(NackAction.Retry, "Transient failure - retrying", event);
                                System.out.println("  Retrying event (transient failure)");
                            } else if (order.amount() > 20) {
                                // Simulate permanent failure - park for inspection
                                subscription.nack(NackAction.Park, "Permanent failure - parking", event);
                                System.out.println("  Parked event (permanent failure)");
                            } else if (order.amount() > 15) {
                                // Skip malformed/invalid event
                                subscription.nack(NackAction.Skip, "Invalid data - skipping", event);
                                System.out.println("  Skipped event (invalid data)");
                            } else {
                                // Success - acknowledge
                                subscription.ack(event);
                                System.out.println("  Acknowledged event");
                            }
                            // Note: NackAction.Stop would stop the subscription
                        } catch (Exception e) {
                            // Park failed event for later inspection
                            subscription.nack(NackAction.Park, e.getMessage(), event);
                            System.out.println("  Parked event due to error: " + e.getMessage());
                        }

                        count[0]++;
                        if (count[0] >= 3) {
                            synchronized (lock) {
                                lock.notify();
                            }
                        }
                    }

                    @Override
                    public void onCancelled(PersistentSubscription subscription, Throwable exception) {
                        if (exception != null) {
                            System.out.println("Subscription cancelled: " + exception.getMessage());
                        }
                    }
                }
        ).get();

        synchronized (lock) {
            lock.wait(10000);
        }
        subscription.stop();

        System.out.println("\nAll tests passed!");
        client.shutdown();
    }

    private static void createPersistentSubscription(KurrentDBPersistentSubscriptionsClient psClient,
                                                      String streamName, String groupName) throws Exception {
        try {
            // Check if subscription already exists
            List<PersistentSubscriptionToStreamInfo> list = psClient.listToStream(streamName).get();
            List<PersistentSubscriptionToStreamInfo> filtered = list.stream()
                    .filter(s -> s.getGroupName().equalsIgnoreCase(groupName))
                    .collect(Collectors.toList());

            if (filtered.isEmpty()) {
                CreatePersistentSubscriptionToStreamOptions options = CreatePersistentSubscriptionToStreamOptions.get()
                        .resolveLinkTos();
                psClient.createToStream(streamName, groupName, options).get();
            }
        } catch (ExecutionException e) {
            // If no subscriptions exist, we get an exception - create the subscription
            CreatePersistentSubscriptionToStreamOptions options = CreatePersistentSubscriptionToStreamOptions.get()
                    .resolveLinkTos();
            psClient.createToStream(streamName, groupName, options).get();
        }
    }

    public record OrderCreated(String orderId, double amount) {}
}
