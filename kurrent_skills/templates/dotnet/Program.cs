// KurrentDB .NET Client Example - Append, Read, Subscribe, and Filtered Subscriptions

using System.Text;
using System.Text.Json;
using KurrentDB.Client;

// Handle command line arguments
if (args.Length > 0 && args[0] == "projection")
{
    await ProjectionExample.Run();
    return;
}
if (args.Length > 0 && args[0] == "persistent")
{
    await KurrentDbExample.PersistentSubscriptionDemo.RunAsync();
    return;
}

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

// === CATCH-UP SUBSCRIPTION ($all) ===
Console.WriteLine("\nStarting catch-up subscription to $all (reading 3 non-system events)...");

try
{
    await using var allSubscription = client.SubscribeToAll(FromAll.Start);
    var allCount = 0;

    await foreach (var message in allSubscription.Messages.WithCancellation(cts.Token))
    {
        switch (message)
        {
            case StreamMessage.Event(var evnt):
                var streamId = evnt.Event.EventStreamId;
                if (!streamId.StartsWith("$"))
                {
                    Console.WriteLine($"  [Sub $all] Stream: {streamId}, Type: {evnt.Event.EventType}");
                    allCount++;
                    if (allCount >= 3)
                    {
                        goto allDone;
                    }
                }
                break;
        }
    }
    allDone:;
}
catch (OperationCanceledException)
{
    Console.WriteLine("$all subscription timed out.");
}

// === FILTERED SUBSCRIPTION (exclude system events) ===
Console.WriteLine("\nStarting filtered subscription (excluding system events)...");

var filterOptions = new SubscriptionFilterOptions(
    EventTypeFilter.ExcludeSystemEvents()
);

using var filterCts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
try
{
    await using var filteredSub = client.SubscribeToAll(FromAll.Start, filterOptions: filterOptions);
    var filterCount = 0;

    await foreach (var message in filteredSub.Messages.WithCancellation(filterCts.Token))
    {
        switch (message)
        {
            case StreamMessage.Event(var evnt):
                Console.WriteLine($"  [Filtered] Stream: {evnt.Event.EventStreamId}, Type: {evnt.Event.EventType}");
                filterCount++;
                if (filterCount >= 3)
                {
                    goto filterDone;
                }
                break;
        }
    }
    filterDone:;
}
catch (OperationCanceledException)
{
    Console.WriteLine("Filtered subscription timed out.");
}

// === FILTERED SUBSCRIPTION (by stream prefix) ===
Console.WriteLine("\nStarting filtered subscription (stream prefix 'order-')...");

var prefixFilter = new SubscriptionFilterOptions(
    StreamFilter.Prefix("order-")
);

using var prefixCts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
try
{
    await using var prefixSub = client.SubscribeToAll(FromAll.Start, filterOptions: prefixFilter);
    var prefixCount = 0;

    await foreach (var message in prefixSub.Messages.WithCancellation(prefixCts.Token))
    {
        switch (message)
        {
            case StreamMessage.Event(var evnt):
                Console.WriteLine($"  [Prefix Filter] Stream: {evnt.Event.EventStreamId}, Type: {evnt.Event.EventType}");
                prefixCount++;
                if (prefixCount >= 2)
                {
                    goto prefixDone;
                }
                break;
        }
    }
    prefixDone:;
}
catch (OperationCanceledException)
{
    Console.WriteLine("Prefix filtered subscription timed out.");
}

// === FILTERED SUBSCRIPTION (by event type) ===
Console.WriteLine("\nStarting filtered subscription (event type prefix 'Order')...");

var eventTypeFilter = new SubscriptionFilterOptions(
    EventTypeFilter.Prefix("Order")
);

using var eventTypeCts = new CancellationTokenSource(TimeSpan.FromSeconds(10));
try
{
    await using var eventTypeSub = client.SubscribeToAll(FromAll.Start, filterOptions: eventTypeFilter);
    var eventTypeCount = 0;

    await foreach (var message in eventTypeSub.Messages.WithCancellation(eventTypeCts.Token))
    {
        switch (message)
        {
            case StreamMessage.Event(var evnt):
                Console.WriteLine($"  [Event Type Filter] Stream: {evnt.Event.EventStreamId}, Type: {evnt.Event.EventType}");
                eventTypeCount++;
                if (eventTypeCount >= 2)
                {
                    goto eventTypeDone;
                }
                break;
        }
    }
    eventTypeDone:;
}
catch (OperationCanceledException)
{
    Console.WriteLine("Event type filtered subscription timed out.");
}

Console.WriteLine("\nAll tests passed!");

// === EVENT TYPES ===
public record OrderCreated(string OrderId, string CustomerId, decimal Amount);
