package com.example.kurrentdb;

import io.kurrent.dbclient.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.nio.charset.StandardCharsets;
import java.util.UUID;
import java.util.concurrent.ExecutionException;

/**
 * KurrentDB Java Client Example - Append, Read, Subscribe, and Filtered Subscriptions
 */
public class Example {

    private static final ObjectMapper mapper = new ObjectMapper();

    public static void main(String[] args) throws Exception {
        // === CONNECTION ===
        String connectionString = System.getenv("KURRENTDB_CONNECTION_STRING");
        if (connectionString == null || connectionString.isEmpty()) {
            connectionString = "kurrentdb://localhost:2113?tls=false";
        }

        KurrentDBClientSettings settings = KurrentDBConnectionString.parseOrThrow(connectionString);
        KurrentDBClient client = KurrentDBClient.create(settings);

        System.out.println("Connected to KurrentDB at " + connectionString);

        // === APPEND EVENTS ===
        String orderId = UUID.randomUUID().toString();
        String streamName = "order-" + orderId;

        OrderCreated order = new OrderCreated(orderId, "customer-123", 99.99);
        byte[] eventData = mapper.writeValueAsBytes(order);

        EventData event = EventData.builderAsJson("OrderCreated", eventData).build();

        WriteResult writeResult = client.appendToStream(streamName, event).get();
        System.out.println("Appended event to " + streamName + " at revision " + writeResult.getNextExpectedRevision());

        // === READ EVENTS ===
        System.out.println("\nReading events:");

        ReadStreamOptions readOptions = ReadStreamOptions.get()
                .forwards()
                .fromStart()
                .maxCount(100);

        ReadResult result = client.readStream(streamName, readOptions).get();

        for (ResolvedEvent resolvedEvent : result.getEvents()) {
            RecordedEvent recordedEvent = resolvedEvent.getOriginalEvent();
            System.out.println("  Event #" + recordedEvent.getRevision() + ": " + recordedEvent.getEventType());
            System.out.println("  Data: " + new String(recordedEvent.getEventData(), StandardCharsets.UTF_8));
        }

        // === CATCH-UP SUBSCRIPTION (Stream) ===
        System.out.println("\nStarting catch-up subscription to stream...");

        SubscribeToStreamOptions subscribeOptions = SubscribeToStreamOptions.get()
                .fromStart()
                .resolveLinkTos();

        final int[] count = {0};
        final Object lock = new Object();

        Subscription subscription = client.subscribeToStream(streamName, new SubscriptionListener() {
            @Override
            public void onEvent(Subscription subscription, ResolvedEvent event) {
                RecordedEvent recordedEvent = event.getOriginalEvent();
                System.out.println("  [Sub] Received: " + recordedEvent.getEventType() +
                        " @ revision " + recordedEvent.getRevision());

                count[0]++;
                if (count[0] >= 1) {
                    synchronized (lock) {
                        lock.notify();
                    }
                }
            }

            @Override
            public void onCancelled(Subscription subscription, Throwable exception) {
                if (exception != null) {
                    System.out.println("Subscription cancelled: " + exception.getMessage());
                }
            }
        }, subscribeOptions).get();

        // Wait for at least one event
        synchronized (lock) {
            lock.wait(5000);
        }
        subscription.stop();

        System.out.println("Subscription stopped");

        // === CATCH-UP SUBSCRIPTION ($all) ===
        System.out.println("\nStarting catch-up subscription to $all (last 5 events)...");

        count[0] = 0;

        SubscribeToAllOptions allOptions = SubscribeToAllOptions.get()
                .fromStart()
                .resolveLinkTos();

        Subscription allSubscription = client.subscribeToAll(new SubscriptionListener() {
            @Override
            public void onEvent(Subscription subscription, ResolvedEvent event) {
                RecordedEvent recordedEvent = event.getOriginalEvent();
                String streamId = recordedEvent.getStreamId();

                if (!streamId.startsWith("$")) {
                    System.out.println("  [Sub] Stream: " + streamId +
                            ", Type: " + recordedEvent.getEventType());

                    count[0]++;
                    if (count[0] >= 5) {
                        synchronized (lock) {
                            lock.notify();
                        }
                    }
                }
            }

            @Override
            public void onCancelled(Subscription subscription, Throwable exception) {
                if (exception != null) {
                    System.out.println("Subscription cancelled: " + exception.getMessage());
                }
            }
        }, allOptions).get();

        synchronized (lock) {
            lock.wait(5000);
        }
        allSubscription.stop();

        // === FILTERED SUBSCRIPTION (exclude system events) ===
        System.out.println("\nStarting filtered subscription (excluding system events)...");

        count[0] = 0;
        String excludeSystemEventsRegex = "^[^\\$].*";

        SubscriptionFilter excludeSystemFilter = SubscriptionFilter.newBuilder()
                .withEventTypeRegularExpression(excludeSystemEventsRegex)
                .build();

        SubscribeToAllOptions filteredOptions = SubscribeToAllOptions.get()
                .fromStart()
                .filter(excludeSystemFilter);

        Subscription filteredSubscription = client.subscribeToAll(new SubscriptionListener() {
            @Override
            public void onEvent(Subscription subscription, ResolvedEvent event) {
                RecordedEvent recordedEvent = event.getOriginalEvent();
                System.out.println("  [Filtered] Stream: " + recordedEvent.getStreamId() +
                        ", Type: " + recordedEvent.getEventType());

                count[0]++;
                if (count[0] >= 3) {
                    synchronized (lock) {
                        lock.notify();
                    }
                }
            }

            @Override
            public void onCancelled(Subscription subscription, Throwable exception) {
                if (exception != null) {
                    System.out.println("Subscription cancelled: " + exception.getMessage());
                }
            }
        }, filteredOptions).get();

        synchronized (lock) {
            lock.wait(5000);
        }
        filteredSubscription.stop();

        // === FILTERED SUBSCRIPTION (by stream prefix) ===
        System.out.println("\nStarting filtered subscription (stream prefix 'order-')...");

        count[0] = 0;

        SubscriptionFilter streamPrefixFilter = SubscriptionFilter.newBuilder()
                .addStreamNamePrefix("order-")
                .build();

        SubscribeToAllOptions prefixOptions = SubscribeToAllOptions.get()
                .fromStart()
                .filter(streamPrefixFilter);

        Subscription prefixSubscription = client.subscribeToAll(new SubscriptionListener() {
            @Override
            public void onEvent(Subscription subscription, ResolvedEvent event) {
                RecordedEvent recordedEvent = event.getOriginalEvent();
                System.out.println("  [Prefix Filter] Stream: " + recordedEvent.getStreamId() +
                        ", Type: " + recordedEvent.getEventType());

                count[0]++;
                if (count[0] >= 2) {
                    synchronized (lock) {
                        lock.notify();
                    }
                }
            }

            @Override
            public void onCancelled(Subscription subscription, Throwable exception) {
                if (exception != null) {
                    System.out.println("Subscription cancelled: " + exception.getMessage());
                }
            }
        }, prefixOptions).get();

        synchronized (lock) {
            lock.wait(5000);
        }
        prefixSubscription.stop();

        // === FILTERED SUBSCRIPTION (by event type prefix) ===
        System.out.println("\nStarting filtered subscription (event type prefix 'Order')...");

        count[0] = 0;

        SubscriptionFilter eventTypeFilter = SubscriptionFilter.newBuilder()
                .addEventTypePrefix("Order")
                .build();

        SubscribeToAllOptions eventTypeOptions = SubscribeToAllOptions.get()
                .fromStart()
                .filter(eventTypeFilter);

        Subscription eventTypeSubscription = client.subscribeToAll(new SubscriptionListener() {
            @Override
            public void onEvent(Subscription subscription, ResolvedEvent event) {
                RecordedEvent recordedEvent = event.getOriginalEvent();
                System.out.println("  [Event Type Filter] Stream: " + recordedEvent.getStreamId() +
                        ", Type: " + recordedEvent.getEventType());

                count[0]++;
                if (count[0] >= 2) {
                    synchronized (lock) {
                        lock.notify();
                    }
                }
            }

            @Override
            public void onCancelled(Subscription subscription, Throwable exception) {
                if (exception != null) {
                    System.out.println("Subscription cancelled: " + exception.getMessage());
                }
            }
        }, eventTypeOptions).get();

        synchronized (lock) {
            lock.wait(5000);
        }
        eventTypeSubscription.stop();

        System.out.println("\nAll tests passed!");
        client.shutdown();
    }

    // Event record
    public record OrderCreated(String orderId, String customerId, double amount) {}
}
