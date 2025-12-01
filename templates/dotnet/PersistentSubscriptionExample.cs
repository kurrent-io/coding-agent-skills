// KurrentDB .NET Client Example - Persistent Subscriptions
// This file is a reference example - copy and adapt for your use case

using System.Text;
using System.Text.Json;
using KurrentDB.Client;

namespace KurrentDbExample;

/// <summary>
/// Demonstrates persistent subscriptions with KurrentDB.
/// Run from Program.cs by calling: await PersistentSubscriptionDemo.RunAsync();
/// </summary>
public static class PersistentSubscriptionDemo
{
    public static async Task RunAsync()
    {
        // === CONNECTION ===
        var connectionString = Environment.GetEnvironmentVariable("KURRENTDB_CONNECTION_STRING")
            ?? "kurrentdb://localhost:2113?tls=false";

        var settings = KurrentDBClientSettings.Create(connectionString);
        await using var client = new KurrentDBClient(settings);
        await using var psClient = new KurrentDBPersistentSubscriptionsClient(settings);

        Console.WriteLine($"Connected to KurrentDB at {connectionString}");

        var streamName = "orders";
        var groupName = "order-processor";

        // === CREATE PERSISTENT SUBSCRIPTION ===
        try
        {
            await psClient.CreateToStreamAsync(
                streamName,
                groupName,
                new PersistentSubscriptionSettings(),
                userCredentials: new UserCredentials("admin", "changeit")
            );
            Console.WriteLine($"Created persistent subscription '{groupName}' on stream '{streamName}'");
        }
        catch (Exception ex) when (ex.Message.Contains("already exists"))
        {
            Console.WriteLine($"Persistent subscription '{groupName}' already exists");
        }

        // === APPEND SOME TEST EVENTS ===
        for (int i = 0; i < 3; i++)
        {
            var orderCreated = new { OrderId = Guid.NewGuid().ToString(), Amount = 10.00m * (i + 1) };
            var eventData = new EventData(
                Uuid.NewUuid(),
                "OrderCreated",
                JsonSerializer.SerializeToUtf8Bytes(orderCreated)
            );
            await client.AppendToStreamAsync(streamName, StreamState.Any, new[] { eventData });
            Console.WriteLine($"Appended OrderCreated event #{i + 1}");
        }

        // === SUBSCRIBE TO PERSISTENT SUBSCRIPTION ===
        Console.WriteLine("\nSubscribing to persistent subscription...");

        using var cts = new CancellationTokenSource(TimeSpan.FromSeconds(30));
        var processedCount = 0;

        try
        {
            await using var subscription = psClient.SubscribeToStream(
                streamName,
                groupName,
                cancellationToken: cts.Token
            );

            await foreach (var message in subscription.Messages.WithCancellation(cts.Token))
            {
                switch (message)
                {
                    case PersistentSubscriptionMessage.Event(var evnt, var retryCount):
                        try
                        {
                            Console.WriteLine($"  Processing: {evnt.Event.EventType} (retry: {retryCount})");
                            Console.WriteLine($"  Data: {Encoding.UTF8.GetString(evnt.Event.Data.Span)}");

                            // Simulate processing
                            await Task.Delay(100);

                            // Acknowledge success
                            await subscription.Ack(evnt);
                            Console.WriteLine($"  Acknowledged event");

                            processedCount++;
                            if (processedCount >= 3)
                            {
                                Console.WriteLine("\nAll tests passed!");
                                return;
                            }
                        }
                        catch (Exception ex)
                        {
                            // Park failed event
                            await subscription.Nack(
                                PersistentSubscriptionNakEventAction.Park,
                                ex.Message,
                                evnt
                            );
                            Console.WriteLine($"  Parked event: {ex.Message}");
                        }
                        break;

                    case PersistentSubscriptionMessage.SubscriptionConfirmation confirmation:
                        Console.WriteLine($"  Subscription confirmed: {confirmation.SubscriptionId}");
                        break;
                }
            }
        }
        catch (OperationCanceledException)
        {
            Console.WriteLine("\nSubscription timed out.");
        }
    }
}
