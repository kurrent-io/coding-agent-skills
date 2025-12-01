// KurrentDB F# Client Example - Append and Read Events

open System
open System.Text
open System.Text.Json
open KurrentDB.Client

type OrderCreated = {
    OrderId: string
    CustomerId: string
    Amount: decimal
}

[<EntryPoint>]
let main args =
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

        printfn "
Reading events:"
        let readResult = client.ReadStreamAsync(Direction.Forwards, streamName, StreamPosition.Start)
        let mutable count = 0
        let enumerator = readResult.GetAsyncEnumerator()
        while! enumerator.MoveNextAsync() do
            let resolvedEvent = enumerator.Current
            count <- count + 1
            printfn "  Event #%d: %s" (resolvedEvent.Event.EventNumber.ToInt64()) resolvedEvent.Event.EventType
            let data = resolvedEvent.Event.Data.ToArray()
            printfn "  Data: %s" (Encoding.UTF8.GetString(data))

        printfn "
Read %d event(s)" count
        printfn "
All tests passed!"
        return 0
    }
    |> Async.AwaitTask
    |> Async.RunSynchronously
