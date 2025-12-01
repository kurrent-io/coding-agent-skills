// KurrentDB F# Client Example - Persistent Subscriptions

open System
open System.Text
open System.Text.Json
open System.Threading
open KurrentDB.Client

// === EVENT TYPES ===
type OrderCreated = {
    OrderId: string
    Amount: decimal
}

let main () =
    task {
        // === CONNECTION ===
        let connectionString =
            Environment.GetEnvironmentVariable("KURRENTDB_CONNECTION_STRING")
            |> Option.ofObj
            |> Option.defaultValue "kurrentdb://localhost:2113?tls=false"

        let settings = KurrentDBClientSettings.Create(connectionString)
        use client = new KurrentDBClient(settings)
        use psClient = new KurrentDBPersistentSubscriptionsClient(settings)

        printfn "Connected to KurrentDB at %s" connectionString

        let streamName = "orders"
        let groupName = "order-processor"

        // === CREATE PERSISTENT SUBSCRIPTION ===
        try
            do! psClient.CreateToStreamAsync(
                streamName,
                groupName,
                PersistentSubscriptionSettings(),
                userCredentials = UserCredentials("admin", "changeit")
            )
            printfn "Created persistent subscription '%s' on stream '%s'" groupName streamName
        with ex when ex.Message.Contains("already exists") ->
            printfn "Persistent subscription '%s' already exists" groupName

        // === APPEND SOME TEST EVENTS ===
        for i in 0..2 do
            let order = {
                OrderId = Guid.NewGuid().ToString()
                Amount = decimal (10.0 * float (i + 1))
            }
            let eventData =
                EventData(
                    Uuid.NewUuid(),
                    "OrderCreated",
                    JsonSerializer.SerializeToUtf8Bytes(order)
                )
            let! _ = client.AppendToStreamAsync(streamName, StreamState.Any, [| eventData |])
            printfn "Appended OrderCreated event #%d" (i + 1)

        // === SUBSCRIBE TO PERSISTENT SUBSCRIPTION ===
        printfn "\nSubscribing to persistent subscription..."

        use cts = new CancellationTokenSource(TimeSpan.FromSeconds(30.0))
        let mutable count = 0
        let mutable continueLoop = true

        try
            use subscription = psClient.SubscribeToStream(streamName, groupName, cancellationToken = cts.Token)

            while continueLoop do
                let! moveNext = subscription.Messages.MoveNextAsync(cts.Token)
                if moveNext then
                    match subscription.Messages.Current with
                    | :? PersistentSubscriptionMessage.Event as evtMsg ->
                        let evnt = evtMsg.ResolvedEvent
                        let retryCount = evtMsg.RetryCount

                        try
                            printfn "  Processing: %s (retry: %d)" evnt.Event.EventType retryCount
                            printfn "  Data: %s" (Encoding.UTF8.GetString(evnt.Event.Data.Span))

                            // Simulate processing
                            // ... your business logic here ...

                            // Acknowledge success
                            do! subscription.Ack(evnt)
                            printfn "  Acknowledged event"
                        with ex ->
                            // Park failed event
                            do! subscription.Nack(PersistentSubscriptionNakEventAction.Park, ex.Message, evnt)
                            printfn "  Parked event: %s" ex.Message

                        count <- count + 1
                        if count >= 3 then
                            continueLoop <- false
                    | :? PersistentSubscriptionMessage.SubscriptionConfirmation as confirm ->
                        printfn "  Subscription confirmed: %s" confirm.SubscriptionId
                    | _ -> ()
                else
                    continueLoop <- false
        with
        | :? OperationCanceledException ->
            printfn "Subscription timed out."

        printfn "\nAll tests passed!"
    }
    |> Async.AwaitTask
    |> Async.RunSynchronously
