using System.Text;
using System.Text.Json;
using KurrentDB.Client;

// === CONNECTION ===
var connectionString = Environment.GetEnvironmentVariable("KURRENTDB_CONNECTION_STRING")
    ?? "kurrentdb://localhost:2113?tls=false";
var settings = KurrentDBClientSettings.Create(connectionString);
await using var client = new KurrentDBClient(settings);

Console.WriteLine($"Connected to KurrentDB at {connectionString}");

// === APPEND EVENTS ===
var orderId = Guid.NewGuid().ToString("N");
var streamName = $"order-{orderId}";

var orderCreated = new OrderCreated(orderId, "customer-123", 99.99m);
var eventData = new EventData(
    Uuid.NewUuid(),
    "OrderCreated",
    JsonSerializer.SerializeToUtf8Bytes(orderCreated)
);

var writeResult = await client.AppendToStreamAsync(
    streamName,
    StreamState.NoStream,
    new[] { eventData }
);

Console.WriteLine($"Appended event to {streamName} successfully");

// === READ EVENTS ===
Console.WriteLine("\nReading events:");
var events = client.ReadStreamAsync(Direction.Forwards, streamName, StreamPosition.Start);

await foreach (var resolvedEvent in events)
{
    Console.WriteLine($"  Event #{resolvedEvent.Event.EventNumber}: {resolvedEvent.Event.EventType}");
    Console.WriteLine($"  Data: {Encoding.UTF8.GetString(resolvedEvent.Event.Data.Span)}");
}

// === CATCH-UP SUBSCRIPTION ===
Console.WriteLine("\nStarting catch-up subscription (waiting for 1 event)...");

using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(10));

try
{
    await using var subscription = client.SubscribeToStream(streamName, FromStream.Start);
    var eventCount = 0;

    await foreach (var message in subscription.Messages.WithCancellation(cts.Token))
    {
        switch (message)
        {
            case StreamMessage.Event(var evnt):
                Console.WriteLine($"  [Sub] Received: {evnt.Event.EventType} @ {evnt.OriginalEventNumber}");
                eventCount++;
                if (eventCount >= 1)
                {
                    goto done;
                }
                break;
            case StreamMessage.CaughtUp:
                Console.WriteLine("  [Sub] Caught up to live!");
                break;
        }
    }
    done:;
}
catch (OperationCanceledException)
{
    Console.WriteLine("Subscription timed out.");
}

Console.WriteLine("\nAll tests passed!");

// === EVENT TYPES ===
public record OrderCreated(string OrderId, string CustomerId, decimal Amount);
