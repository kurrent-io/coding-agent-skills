package com.example.kurrentdb;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import io.kurrent.dbclient.*;

import java.util.*;
import java.util.concurrent.ConcurrentHashMap;
import java.util.function.BiFunction;

/**
 * KurrentDB Java In-Memory Projection Example
 * Demonstrates: Subscribe to events, build state, track checkpoint
 */
public class ProjectionExample {

    // === MINIMAL PROJECTION FRAMEWORK ===
    public static class Projection {
        private final String name;
        private final Map<String, Map<String, Object>> state = new ConcurrentHashMap<>();
        private Position checkpoint;
        private final Map<String, BiFunction<Map<String, Object>, JsonNode, Map<String, Object>>> handlers = new HashMap<>();
        private final ObjectMapper mapper = new ObjectMapper();

        public Projection(String name) {
            this.name = name;
        }

        public Projection on(String eventType, BiFunction<Map<String, Object>, JsonNode, Map<String, Object>> handler) {
            handlers.put(eventType, handler);
            return this;
        }

        public Map<String, Object> get(String streamId) {
            return state.get(streamId);
        }

        public Map<String, Map<String, Object>> getAll() {
            return new HashMap<>(state);
        }

        public boolean apply(ResolvedEvent resolved) {
            RecordedEvent event = resolved.getEvent();
            BiFunction<Map<String, Object>, JsonNode, Map<String, Object>> handler = handlers.get(event.getEventType());
            if (handler == null) {
                return false;
            }

            String streamId = event.getStreamId();
            Map<String, Object> current = state.getOrDefault(streamId, new HashMap<>());

            try {
                JsonNode data = mapper.readTree(event.getEventData());
                state.put(streamId, handler.apply(current, data));
                checkpoint = event.getPosition();
                return true;
            } catch (Exception e) {
                e.printStackTrace();
                return false;
            }
        }

        public Position getCheckpoint() {
            return checkpoint;
        }

        public String getName() {
            return name;
        }
    }

    public static void main(String[] args) throws Exception {
        run();
    }

    public static void run() throws Exception {
        // === SETUP ===
        String connectionString = System.getenv("KURRENTDB_CONNECTION_STRING");
        if (connectionString == null || connectionString.isEmpty()) {
            connectionString = "esdb://localhost:2113?tls=false";
        }

        KurrentDBClientSettings settings = KurrentDBConnectionString.parseOrThrow(connectionString);
        KurrentDBClient client = KurrentDBClient.create(settings);
        System.out.println("Connected to KurrentDB at " + connectionString);

        ObjectMapper mapper = new ObjectMapper();

        // === DEFINE PROJECTION ===
        Projection orderProjection = new Projection("OrderSummary")
            .on("OrderCreated", (state, data) -> {
                Map<String, Object> newState = new HashMap<>();
                newState.put("orderId", data.has("orderId") ? data.get("orderId").asText() : null);
                newState.put("customerId", data.has("customerId") ? data.get("customerId").asText() : null);
                newState.put("amount", data.has("amount") ? data.get("amount").asDouble() : 0.0);
                newState.put("status", "created");
                newState.put("items", new ArrayList<String>());
                return newState;
            })
            .on("ItemAdded", (state, data) -> {
                @SuppressWarnings("unchecked")
                List<String> items = (List<String>) state.get("items");
                if (items != null && data.has("item")) {
                    items.add(data.get("item").asText());
                }
                if (data.has("price")) {
                    Double currentAmount = (Double) state.getOrDefault("amount", 0.0);
                    state.put("amount", currentAmount + data.get("price").asDouble());
                }
                return state;
            })
            .on("OrderShipped", (state, data) -> {
                state.put("status", "shipped");
                state.put("shippedAt", data.has("shippedAt") ? data.get("shippedAt").asText() : null);
                return state;
            })
            .on("OrderCompleted", (state, data) -> {
                state.put("status", "completed");
                return state;
            });

        // === TEST: Append test events ===
        System.out.println("\n=== Appending test events ===");

        String orderId1 = UUID.randomUUID().toString();
        String orderId2 = UUID.randomUUID().toString();
        String stream1 = "order-" + orderId1;
        String stream2 = "order-" + orderId2;

        // Order 1: Created -> ItemAdded -> Shipped -> Completed
        appendEvent(client, mapper, stream1, "OrderCreated",
            Map.of("orderId", orderId1, "customerId", "cust-1", "amount", 100.0));
        appendEvent(client, mapper, stream1, "ItemAdded",
            Map.of("item", "Widget", "price", 25.0));
        appendEvent(client, mapper, stream1, "OrderShipped",
            Map.of("shippedAt", "2024-01-15T10:00:00Z"));
        appendEvent(client, mapper, stream1, "OrderCompleted", Map.of());

        // Order 2: Created -> ItemAdded (still pending)
        appendEvent(client, mapper, stream2, "OrderCreated",
            Map.of("orderId", orderId2, "customerId", "cust-2", "amount", 50.0));
        appendEvent(client, mapper, stream2, "ItemAdded",
            Map.of("item", "Gadget", "price", 30.0));

        System.out.println("Created order streams: " + stream1 + ", " + stream2);

        // === RUN PROJECTION ===
        System.out.println("\n=== Running projection ===");

        // Build regex to exclude system events
        String excludeSystemEventsRegex = "^[^\\$].*";
        SubscriptionFilter filter = SubscriptionFilter.newBuilder()
            .withEventTypeRegularExpression(excludeSystemEventsRegex)
            .build();

        SubscribeToAllOptions options = SubscribeToAllOptions.get()
            .fromStart()
            .filter(filter);

        final int[] processedCount = {0};
        Set<String> targetStreams = new HashSet<>(Arrays.asList(stream1, stream2));
        Map<String, Integer> targetEventsCount = new HashMap<>();
        targetEventsCount.put(stream1, 0);
        targetEventsCount.put(stream2, 0);
        Map<String, Integer> expectedCounts = Map.of(stream1, 4, stream2, 2);

        Subscription subscription = client.subscribeToAll(new SubscriptionListener() {
            @Override
            public void onEvent(Subscription sub, ResolvedEvent resolved) {
                if (orderProjection.apply(resolved)) {
                    processedCount[0]++;
                    String streamId = resolved.getEvent().getStreamId();
                    System.out.println("  Processed: " + resolved.getEvent().getEventType() +
                        " on " + streamId);

                    if (targetStreams.contains(streamId)) {
                        targetEventsCount.merge(streamId, 1, Integer::sum);
                    }
                }

                // Stop when we've processed all our test events for both streams
                if (targetEventsCount.get(stream1) >= expectedCounts.get(stream1) &&
                    targetEventsCount.get(stream2) >= expectedCounts.get(stream2)) {
                    sub.stop();
                }

                // Safety limit
                if (processedCount[0] > 200) {
                    sub.stop();
                }
            }

            @Override
            public void onCancelled(Subscription sub, Throwable throwable) {
                if (throwable != null) {
                    System.err.println("Subscription cancelled: " + throwable.getMessage());
                }
            }
        }, options).get();

        // Wait for subscription to process
        Thread.sleep(5000);
        subscription.stop();

        // === VERIFY RESULTS ===
        System.out.println("\n=== Projection Results ===");

        Map<String, Object> order1State = orderProjection.get(stream1);
        Map<String, Object> order2State = orderProjection.get(stream2);

        System.out.println("\nOrder 1 (" + stream1 + "):");
        System.out.println(mapper.writerWithDefaultPrettyPrinter().writeValueAsString(order1State));

        System.out.println("\nOrder 2 (" + stream2 + "):");
        System.out.println(mapper.writerWithDefaultPrettyPrinter().writeValueAsString(order2State));

        // === ASSERTIONS ===
        System.out.println("\n=== Running assertions ===");

        boolean passed = true;

        // Order 1 assertions
        if (!"completed".equals(order1State.get("status"))) {
            System.out.println("FAIL: Order 1 status should be 'completed', got '" + order1State.get("status") + "'");
            passed = false;
        }
        if ((Double) order1State.get("amount") != 125.0) {
            System.out.println("FAIL: Order 1 amount should be 125, got " + order1State.get("amount"));
            passed = false;
        }
        @SuppressWarnings("unchecked")
        List<String> items1 = (List<String>) order1State.get("items");
        if (items1.size() != 1) {
            System.out.println("FAIL: Order 1 should have 1 item, got " + items1.size());
            passed = false;
        }

        // Order 2 assertions
        if (!"created".equals(order2State.get("status"))) {
            System.out.println("FAIL: Order 2 status should be 'created', got '" + order2State.get("status") + "'");
            passed = false;
        }
        if ((Double) order2State.get("amount") != 80.0) {
            System.out.println("FAIL: Order 2 amount should be 80, got " + order2State.get("amount"));
            passed = false;
        }

        // Checkpoint assertion
        if (orderProjection.getCheckpoint() == null) {
            System.out.println("FAIL: Checkpoint should be set");
            passed = false;
        }

        if (passed) {
            System.out.println("\nAll projection tests passed!");
        } else {
            System.out.println("\nSome tests failed!");
            System.exit(1);
        }

        client.shutdown();
    }

    private static void appendEvent(KurrentDBClient client, ObjectMapper mapper, String stream, String type, Map<String, Object> data) throws Exception {
        byte[] jsonData = mapper.writeValueAsBytes(data);
        EventData eventData = EventData.builderAsJson(type, jsonData).build();
        client.appendToStream(stream, eventData).get();
    }
}
