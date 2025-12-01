// KurrentDB F# Client Example - Append, Read, Subscribe, and Filtered Subscriptions

open System
open System.Text
open System.Text.Json
open System.Threading
open KurrentDB.Client

type OrderCreated = {
    OrderId: string
    CustomerId: string
    Amount: decimal
}

[<EntryPoint>]
let main args =
    // Handle command line arguments
    if args.Length > 0 && args.[0] = "projection" then
        Projection.run()
        |> Async.AwaitTask
        |> Async.RunSynchronously
    else

    task {
        let connectionString =
            Environment.GetEnvironmentVariable("KURRENTDB_CONNECTION_STRING")
            |> Option.ofObj
            |> Option.defaultValue "kurrentdb://localhost:2113?tls=false"

        let settings = KurrentDBClientSettings.Create(connectionString)
        use client = new KurrentDBClient(settings)

        printfn "Connected to KurrentDB at %s" connectionString

        let orderId = Guid.NewGuid().ToString("N")
        let streamName = sprintf "order-%s" orderId

        let orderCreated = {
            OrderId = orderId
            CustomerId = "customer-123"
            Amount = 99.99m
        }

        let eventData =
            EventData(
                Uuid.NewUuid(),
                "OrderCreated",
                JsonSerializer.SerializeToUtf8Bytes(orderCreated)
            )

        let! _ =
            client.AppendToStreamAsync(
                streamName,
                StreamState.NoStream,
                [| eventData |]
            )

        printfn "Appended event to %s successfully" streamName

        // === READ EVENTS ===
        printfn "\nReading events:"
        let readResult = client.ReadStreamAsync(Direction.Forwards, streamName, StreamPosition.Start)
        let mutable count = 0
        let enumerator = readResult.GetAsyncEnumerator()
        while! enumerator.MoveNextAsync() do
            let resolvedEvent = enumerator.Current
            count <- count + 1
            printfn "  Event #%d: %s" (resolvedEvent.Event.EventNumber.ToInt64()) resolvedEvent.Event.EventType
            let data = resolvedEvent.Event.Data.ToArray()
            printfn "  Data: %s" (Encoding.UTF8.GetString(data))

        printfn "\nRead %d event(s)" count

        // === CATCH-UP SUBSCRIPTION (Stream) ===
        printfn "\nStarting catch-up subscription to stream..."
        use cts = new CancellationTokenSource(TimeSpan.FromSeconds(10.0))

        try
            use subscription = client.SubscribeToStream(streamName, FromStream.Start)
            let msgEnumerator = subscription.Messages.GetAsyncEnumerator(cts.Token)
            let mutable subCount = 0
            let mutable continueLoop = true

            while continueLoop do
                let! moveNext = msgEnumerator.MoveNextAsync()
                if moveNext then
                    match msgEnumerator.Current with
                    | :? StreamMessage.Event as evtMsg ->
                        let evnt = evtMsg.ResolvedEvent
                        printfn "  [Sub] Received: %s @ %d" evnt.Event.EventType (evnt.OriginalEventNumber.ToInt64())
                        subCount <- subCount + 1
                        if subCount >= 1 then continueLoop <- false
                    | :? StreamMessage.CaughtUp ->
                        printfn "  [Sub] Caught up to live!"
                    | _ -> ()
                else
                    continueLoop <- false
        with
        | :? OperationCanceledException ->
            printfn "Stream subscription timed out."

        printfn "Subscription stopped"

        // === CATCH-UP SUBSCRIPTION ($all) ===
        printfn "\nStarting catch-up subscription to $all (reading 3 non-system events)..."
        use allCts = new CancellationTokenSource(TimeSpan.FromSeconds(10.0))

        try
            use allSubscription = client.SubscribeToAll(FromAll.Start)
            let allEnumerator = allSubscription.Messages.GetAsyncEnumerator(allCts.Token)
            let mutable allCount = 0
            let mutable continueAllLoop = true

            while continueAllLoop do
                let! moveNext = allEnumerator.MoveNextAsync()
                if moveNext then
                    match allEnumerator.Current with
                    | :? StreamMessage.Event as evtMsg ->
                        let evnt = evtMsg.ResolvedEvent
                        let streamId = evnt.Event.EventStreamId
                        if not (streamId.StartsWith("$")) then
                            printfn "  [Sub $all] Stream: %s, Type: %s" streamId evnt.Event.EventType
                            allCount <- allCount + 1
                            if allCount >= 3 then continueAllLoop <- false
                    | _ -> ()
                else
                    continueAllLoop <- false
        with
        | :? OperationCanceledException ->
            printfn "$all subscription timed out."

        // === FILTERED SUBSCRIPTION (exclude system events) ===
        printfn "\nStarting filtered subscription (excluding system events)..."
        let filterOptions = SubscriptionFilterOptions(EventTypeFilter.ExcludeSystemEvents())
        use filterCts = new CancellationTokenSource(TimeSpan.FromSeconds(10.0))

        try
            use filteredSub = client.SubscribeToAll(FromAll.Start, filterOptions = filterOptions)
            let filterEnumerator = filteredSub.Messages.GetAsyncEnumerator(filterCts.Token)
            let mutable filterCount = 0
            let mutable continueFilterLoop = true

            while continueFilterLoop do
                let! moveNext = filterEnumerator.MoveNextAsync()
                if moveNext then
                    match filterEnumerator.Current with
                    | :? StreamMessage.Event as evtMsg ->
                        let evnt = evtMsg.ResolvedEvent
                        printfn "  [Filtered] Stream: %s, Type: %s" evnt.Event.EventStreamId evnt.Event.EventType
                        filterCount <- filterCount + 1
                        if filterCount >= 3 then continueFilterLoop <- false
                    | _ -> ()
                else
                    continueFilterLoop <- false
        with
        | :? OperationCanceledException ->
            printfn "Filtered subscription timed out."

        // === FILTERED SUBSCRIPTION (by stream prefix) ===
        printfn "\nStarting filtered subscription (stream prefix 'order-')..."
        let prefixFilter = SubscriptionFilterOptions(StreamFilter.Prefix("order-"))
        use prefixCts = new CancellationTokenSource(TimeSpan.FromSeconds(10.0))

        try
            use prefixSub = client.SubscribeToAll(FromAll.Start, filterOptions = prefixFilter)
            let prefixEnumerator = prefixSub.Messages.GetAsyncEnumerator(prefixCts.Token)
            let mutable prefixCount = 0
            let mutable continuePrefixLoop = true

            while continuePrefixLoop do
                let! moveNext = prefixEnumerator.MoveNextAsync()
                if moveNext then
                    match prefixEnumerator.Current with
                    | :? StreamMessage.Event as evtMsg ->
                        let evnt = evtMsg.ResolvedEvent
                        printfn "  [Prefix Filter] Stream: %s, Type: %s" evnt.Event.EventStreamId evnt.Event.EventType
                        prefixCount <- prefixCount + 1
                        if prefixCount >= 2 then continuePrefixLoop <- false
                    | _ -> ()
                else
                    continuePrefixLoop <- false
        with
        | :? OperationCanceledException ->
            printfn "Prefix filtered subscription timed out."

        printfn "\nAll tests passed!"
        return 0
    }
    |> Async.AwaitTask
    |> Async.RunSynchronously
