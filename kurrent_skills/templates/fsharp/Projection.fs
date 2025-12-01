// KurrentDB F# In-Memory Projection Example
// Demonstrates: Subscribe to events, build state, track checkpoint

module Projection

open System
open System.Collections.Generic
open System.Text
open System.Text.Json
open System.Threading
open KurrentDB.Client

// === MINIMAL PROJECTION FRAMEWORK ===

type EventHandler<'TState> = 'TState -> JsonElement -> 'TState

type Projection<'TState when 'TState : (new : unit -> 'TState)> = {
    Name: string
    mutable State: Dictionary<string, 'TState>
    mutable Checkpoint: Position option
    Handlers: Dictionary<string, EventHandler<'TState>>
}

module Projection =
    let create<'TState when 'TState : (new : unit -> 'TState)> name : Projection<'TState> =
        {
            Name = name
            State = Dictionary<string, 'TState>()
            Checkpoint = None
            Handlers = Dictionary<string, EventHandler<'TState>>()
        }

    let on eventType (handler: EventHandler<'TState>) (projection: Projection<'TState>) =
        projection.Handlers.[eventType] <- handler
        projection

    let get streamId (projection: Projection<'TState>) =
        match projection.State.TryGetValue(streamId) with
        | true, state -> Some state
        | false, _ -> None

    let apply (resolved: ResolvedEvent) (projection: Projection<'TState>) =
        let evt = resolved.Event
        match projection.Handlers.TryGetValue(evt.EventType) with
        | true, handler ->
            let streamId = evt.EventStreamId
            let current =
                match projection.State.TryGetValue(streamId) with
                | true, s -> s
                | false, _ -> new 'TState()
            let data = JsonDocument.Parse(evt.Data.ToArray()).RootElement
            projection.State.[streamId] <- handler current data
            projection.Checkpoint <- Some evt.Position
            true
        | false, _ -> false

// === ORDER STATE ===

type OrderState() =
    member val OrderId = "" with get, set
    member val CustomerId = "" with get, set
    member val Amount = 0m with get, set
    member val Status = "unknown" with get, set
    member val Items = ResizeArray<string>() with get, set
    member val ShippedAt = "" with get, set

// === RUN PROJECTION ===

let run () =
    task {
        // === SETUP ===
        let connectionString =
            Environment.GetEnvironmentVariable("KURRENTDB_CONNECTION_STRING")
            |> Option.ofObj
            |> Option.defaultValue "kurrentdb://localhost:2113?tls=false"

        let settings = KurrentDBClientSettings.Create(connectionString)
        use client = new KurrentDBClient(settings)
        printfn "Connected to KurrentDB at %s" connectionString

        // Helper for safe property access
        let tryGetString (prop: string) (data: JsonElement) =
            match data.TryGetProperty(prop) with
            | true, el -> el.GetString()
            | false, _ -> ""
        let tryGetDecimal (prop: string) (data: JsonElement) =
            match data.TryGetProperty(prop) with
            | true, el -> el.GetDecimal()
            | false, _ -> 0m

        // === DEFINE PROJECTION ===
        let orderProjection =
            Projection.create<OrderState> "OrderSummary"
            |> Projection.on "OrderCreated" (fun _ data ->
                let state = OrderState()
                state.OrderId <- tryGetString "orderId" data
                state.CustomerId <- tryGetString "customerId" data
                state.Amount <- tryGetDecimal "amount" data
                state.Status <- "created"
                state)
            |> Projection.on "ItemAdded" (fun state data ->
                match data.TryGetProperty("item") with
                | true, el -> state.Items.Add(el.GetString())
                | false, _ -> ()
                state.Amount <- state.Amount + tryGetDecimal "price" data
                state)
            |> Projection.on "OrderShipped" (fun state data ->
                state.Status <- "shipped"
                state.ShippedAt <- tryGetString "shippedAt" data
                state)
            |> Projection.on "OrderCompleted" (fun state _ ->
                state.Status <- "completed"
                state)

        // === TEST: Append test events ===
        printfn "\n=== Appending test events ==="

        let orderId1 = Guid.NewGuid().ToString()
        let orderId2 = Guid.NewGuid().ToString()
        let stream1 = sprintf "order-%s" orderId1
        let stream2 = sprintf "order-%s" orderId2

        let makeEvent eventType (data: obj) =
            EventData(
                Uuid.NewUuid(),
                eventType,
                JsonSerializer.SerializeToUtf8Bytes(data)
            )

        // Order 1: Created -> ItemAdded -> Shipped -> Completed
        let! _ = client.AppendToStreamAsync(stream1, StreamState.Any, [|
            makeEvent "OrderCreated" {| orderId = orderId1; customerId = "cust-1"; amount = 100m |}
        |])
        let! _ = client.AppendToStreamAsync(stream1, StreamState.Any, [|
            makeEvent "ItemAdded" {| item = "Widget"; price = 25m |}
        |])
        let! _ = client.AppendToStreamAsync(stream1, StreamState.Any, [|
            makeEvent "OrderShipped" {| shippedAt = "2024-01-15T10:00:00Z" |}
        |])
        let! _ = client.AppendToStreamAsync(stream1, StreamState.Any, [|
            makeEvent "OrderCompleted" {||}
        |])

        // Order 2: Created -> ItemAdded (still pending)
        let! _ = client.AppendToStreamAsync(stream2, StreamState.Any, [|
            makeEvent "OrderCreated" {| orderId = orderId2; customerId = "cust-2"; amount = 50m |}
        |])
        let! _ = client.AppendToStreamAsync(stream2, StreamState.Any, [|
            makeEvent "ItemAdded" {| item = "Gadget"; price = 30m |}
        |])

        printfn "Created order streams: %s, %s" stream1 stream2

        // === RUN PROJECTION ===
        printfn "\n=== Running projection ==="

        let filterOptions = SubscriptionFilterOptions(EventTypeFilter.ExcludeSystemEvents())
        use cts = new CancellationTokenSource(TimeSpan.FromSeconds(30.0))

        use subscription = client.SubscribeToAll(FromAll.Start, filterOptions = filterOptions)
        let enumerator = subscription.Messages.GetAsyncEnumerator(cts.Token)

        let mutable processedCount = 0
        let targetStreams = HashSet([stream1; stream2])
        let targetEventsCount = Dictionary<string, int>()
        targetEventsCount.[stream1] <- 0
        targetEventsCount.[stream2] <- 0
        let expectedCounts = dict [stream1, 4; stream2, 2] // Order 1: 4 events, Order 2: 2 events
        let mutable continueLoop = true

        while continueLoop do
            let! moveNext = enumerator.MoveNextAsync()
            if moveNext then
                match enumerator.Current with
                | :? StreamMessage.Event as evtMsg ->
                    let resolved = evtMsg.ResolvedEvent
                    if Projection.apply resolved orderProjection then
                        processedCount <- processedCount + 1
                        let streamId = resolved.Event.EventStreamId
                        printfn "  Processed: %s on %s" resolved.Event.EventType streamId

                        if targetStreams.Contains(streamId) then
                            targetEventsCount.[streamId] <- targetEventsCount.[streamId] + 1

                    // Stop when we've processed all test events for both streams
                    if targetEventsCount.[stream1] >= expectedCounts.[stream1] &&
                       targetEventsCount.[stream2] >= expectedCounts.[stream2] then
                        continueLoop <- false

                    // Safety limit
                    if processedCount > 200 then
                        continueLoop <- false
                | _ -> ()
            else
                continueLoop <- false

        // === VERIFY RESULTS ===
        printfn "\n=== Projection Results ==="

        let order1State = Projection.get stream1 orderProjection
        let order2State = Projection.get stream2 orderProjection

        match order1State with
        | Some s ->
            printfn "\nOrder 1 (%s):" stream1
            printfn "  OrderId: %s" s.OrderId
            printfn "  CustomerId: %s" s.CustomerId
            printfn "  Amount: %M" s.Amount
            printfn "  Status: %s" s.Status
            printfn "  Items: %A" (s.Items |> Seq.toList)
        | None -> printfn "\nOrder 1 not found"

        match order2State with
        | Some s ->
            printfn "\nOrder 2 (%s):" stream2
            printfn "  OrderId: %s" s.OrderId
            printfn "  CustomerId: %s" s.CustomerId
            printfn "  Amount: %M" s.Amount
            printfn "  Status: %s" s.Status
            printfn "  Items: %A" (s.Items |> Seq.toList)
        | None -> printfn "\nOrder 2 not found"

        // === ASSERTIONS ===
        printfn "\n=== Running assertions ==="

        let mutable passed = true

        // Order 1 assertions
        match order1State with
        | Some s ->
            if s.Status <> "completed" then
                printfn "FAIL: Order 1 status should be 'completed', got '%s'" s.Status
                passed <- false
            if s.Amount <> 125m then
                printfn "FAIL: Order 1 amount should be 125, got %M" s.Amount
                passed <- false
            if s.Items.Count <> 1 then
                printfn "FAIL: Order 1 should have 1 item, got %d" s.Items.Count
                passed <- false
        | None ->
            printfn "FAIL: Order 1 state not found"
            passed <- false

        // Order 2 assertions
        match order2State with
        | Some s ->
            if s.Status <> "created" then
                printfn "FAIL: Order 2 status should be 'created', got '%s'" s.Status
                passed <- false
            if s.Amount <> 80m then
                printfn "FAIL: Order 2 amount should be 80, got %M" s.Amount
                passed <- false
        | None ->
            printfn "FAIL: Order 2 state not found"
            passed <- false

        // Checkpoint assertion
        if orderProjection.Checkpoint.IsNone then
            printfn "FAIL: Checkpoint should be set"
            passed <- false

        if passed then
            printfn "\nAll projection tests passed!"
            return 0
        else
            printfn "\nSome tests failed!"
            return 1
    }
