// KurrentDB .NET In-Memory Projection Example
// Demonstrates: Subscribe to events, build state, track checkpoint

using System.Text;
using System.Text.Json;
using KurrentDB.Client;

// === MINIMAL PROJECTION FRAMEWORK ===
public class Projection<TState> where TState : class, new()
{
    public string Name { get; }
    public Dictionary<string, TState> State { get; } = new();
    public Position? Checkpoint { get; private set; }

    private readonly Dictionary<string, Func<TState, JsonElement, TState>> _handlers = new();

    public Projection(string name) => Name = name;

    public Projection<TState> On(string eventType, Func<TState, JsonElement, TState> handler)
    {
        _handlers[eventType] = handler;
        return this;
    }

    public TState? Get(string streamId) => State.GetValueOrDefault(streamId);

    public Dictionary<string, TState> GetAll() => new(State);

    public bool Apply(ResolvedEvent resolved)
    {
        var evt = resolved.Event;
        if (!_handlers.TryGetValue(evt.EventType, out var handler))
            return false;

        var streamId = evt.EventStreamId;
        var current = State.GetValueOrDefault(streamId) ?? new TState();
        var data = JsonDocument.Parse(evt.Data.ToArray()).RootElement;
        State[streamId] = handler(current, data);
        Checkpoint = evt.Position;
        return true;
    }
}

// === ORDER STATE ===
public class OrderState
{
    public string? OrderId { get; set; }
    public string? CustomerId { get; set; }
    public decimal Amount { get; set; }
    public string Status { get; set; } = "unknown";
    public List<string> Items { get; set; } = new();
    public string? ShippedAt { get; set; }
}

// === MAIN ===
public static class ProjectionExample
{
    public static async Task Run()
    {
        // === SETUP ===
        var connectionString = Environment.GetEnvironmentVariable("KURRENTDB_CONNECTION_STRING")
            ?? "kurrentdb://localhost:2113?tls=false";

        var settings = KurrentDBClientSettings.Create(connectionString);
        await using var client = new KurrentDBClient(settings);
        Console.WriteLine($"Connected to KurrentDB at {connectionString}");

        // === DEFINE PROJECTION ===
        var orderProjection = new Projection<OrderState>("OrderSummary")
            .On("OrderCreated", (state, data) => new OrderState
            {
                OrderId = data.TryGetProperty("orderId", out var oid) ? oid.GetString() : null,
                CustomerId = data.TryGetProperty("customerId", out var cid) ? cid.GetString() : null,
                Amount = data.TryGetProperty("amount", out var amt) ? amt.GetDecimal() : 0m,
                Status = "created",
                Items = new List<string>()
            })
            .On("ItemAdded", (state, data) =>
            {
                if (data.TryGetProperty("item", out var item))
                    state.Items.Add(item.GetString()!);
                if (data.TryGetProperty("price", out var price))
                    state.Amount += price.GetDecimal();
                return state;
            })
            .On("OrderShipped", (state, data) =>
            {
                state.Status = "shipped";
                state.ShippedAt = data.TryGetProperty("shippedAt", out var sa) ? sa.GetString() : null;
                return state;
            })
            .On("OrderCompleted", (state, _) =>
            {
                state.Status = "completed";
                return state;
            });

        // === TEST: Append test events ===
        Console.WriteLine("\n=== Appending test events ===");

        var orderId1 = Guid.NewGuid().ToString();
        var orderId2 = Guid.NewGuid().ToString();
        var stream1 = $"order-{orderId1}";
        var stream2 = $"order-{orderId2}";

        EventData MakeEvent(string type, object data) => new(
            Uuid.NewUuid(),
            type,
            Encoding.UTF8.GetBytes(JsonSerializer.Serialize(data))
        );

        // Order 1: Created -> ItemAdded -> Shipped -> Completed
        await client.AppendToStreamAsync(stream1, StreamState.Any, new[] {
            MakeEvent("OrderCreated", new { orderId = orderId1, customerId = "cust-1", amount = 100m })
        });
        await client.AppendToStreamAsync(stream1, StreamState.Any, new[] {
            MakeEvent("ItemAdded", new { item = "Widget", price = 25m })
        });
        await client.AppendToStreamAsync(stream1, StreamState.Any, new[] {
            MakeEvent("OrderShipped", new { shippedAt = "2024-01-15T10:00:00Z" })
        });
        await client.AppendToStreamAsync(stream1, StreamState.Any, new[] {
            MakeEvent("OrderCompleted", new { })
        });

        // Order 2: Created -> ItemAdded (still pending)
        await client.AppendToStreamAsync(stream2, StreamState.Any, new[] {
            MakeEvent("OrderCreated", new { orderId = orderId2, customerId = "cust-2", amount = 50m })
        });
        await client.AppendToStreamAsync(stream2, StreamState.Any, new[] {
            MakeEvent("ItemAdded", new { item = "Gadget", price = 30m })
        });

        Console.WriteLine($"Created order streams: {stream1}, {stream2}");

        // === RUN PROJECTION ===
        Console.WriteLine("\n=== Running projection ===");

        var processedCount = 0;
        var targetStreams = new HashSet<string> { stream1, stream2 };
        var targetEventsCount = new Dictionary<string, int> { { stream1, 0 }, { stream2, 0 } };
        var expectedCounts = new Dictionary<string, int> { { stream1, 4 }, { stream2, 2 } };

        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(30));
        var filterOptions = new SubscriptionFilterOptions(EventTypeFilter.ExcludeSystemEvents());

        await using var subscription = client.SubscribeToAll(FromAll.Start, filterOptions: filterOptions);

        await foreach (var message in subscription.Messages.WithCancellation(cts.Token))
        {
            if (message is StreamMessage.Event evtMsg)
            {
                var resolved = evtMsg.ResolvedEvent;
                if (orderProjection.Apply(resolved))
                {
                    processedCount++;
                    Console.WriteLine($"  Processed: {resolved.Event.EventType} on {resolved.Event.EventStreamId}");

                    if (targetStreams.Contains(resolved.Event.EventStreamId))
                        targetEventsCount[resolved.Event.EventStreamId]++;
                }

                // Stop when we've processed our test events
                if (targetEventsCount[stream1] >= expectedCounts[stream1] &&
                    targetEventsCount[stream2] >= expectedCounts[stream2])
                    break;

                // Safety limit
                if (processedCount > 100) break;
            }
        }

        // === VERIFY RESULTS ===
        Console.WriteLine("\n=== Projection Results ===");

        var order1State = orderProjection.Get(stream1);
        var order2State = orderProjection.Get(stream2);

        Console.WriteLine($"\nOrder 1 ({stream1}):");
        Console.WriteLine(JsonSerializer.Serialize(order1State, new JsonSerializerOptions { WriteIndented = true }));

        Console.WriteLine($"\nOrder 2 ({stream2}):");
        Console.WriteLine(JsonSerializer.Serialize(order2State, new JsonSerializerOptions { WriteIndented = true }));

        // === ASSERTIONS ===
        Console.WriteLine("\n=== Running assertions ===");

        var passed = true;

        // Order 1 assertions
        if (order1State?.Status != "completed")
        {
            Console.WriteLine($"FAIL: Order 1 status should be 'completed', got '{order1State?.Status}'");
            passed = false;
        }
        if (order1State?.Amount != 125m)
        {
            Console.WriteLine($"FAIL: Order 1 amount should be 125, got {order1State?.Amount}");
            passed = false;
        }
        if (order1State?.Items.Count != 1)
        {
            Console.WriteLine($"FAIL: Order 1 should have 1 item, got {order1State?.Items.Count}");
            passed = false;
        }

        // Order 2 assertions
        if (order2State?.Status != "created")
        {
            Console.WriteLine($"FAIL: Order 2 status should be 'created', got '{order2State?.Status}'");
            passed = false;
        }
        if (order2State?.Amount != 80m)
        {
            Console.WriteLine($"FAIL: Order 2 amount should be 80, got {order2State?.Amount}");
            passed = false;
        }

        // Checkpoint assertion
        if (orderProjection.Checkpoint == null)
        {
            Console.WriteLine("FAIL: Checkpoint should be set");
            passed = false;
        }

        if (passed)
        {
            Console.WriteLine("\nAll projection tests passed!");
        }
        else
        {
            Console.WriteLine("\nSome tests failed!");
            Environment.Exit(1);
        }
    }
}
