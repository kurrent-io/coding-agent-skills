# KurrentDB Client Reference

Complete API reference for all KurrentDB client libraries.

## Table of Contents
1. [Docker Setup](#docker-setup)
2. [.NET Client](#net-client)
3. [F# Client](#f-client)
4. [Java Client](#java-client)
5. [Python Client](#python-client)
6. [Node.js Client](#nodejs-client)
7. [Go Client](#go-client)
8. [Rust Client](#rust-client)

---

## Docker Setup

### Quick Start (Docker Run)

```bash
docker run --name kurrentdb-node -it -p 2113:2113 \
    docker.kurrent.io/kurrent-latest/kurrentdb:latest \
    --insecure --run-projections=All --enable-atom-pub-over-http
```

### Docker Compose

```yaml
services:
  kurrentdb:
    image: docker.kurrent.io/kurrent-latest/kurrentdb:latest
    container_name: kurrentdb
    environment:
      - KURRENTDB_CLUSTER_SIZE=1
      - KURRENTDB_RUN_PROJECTIONS=All
      - KURRENTDB_START_STANDARD_PROJECTIONS=true
      - KURRENTDB_NODE_PORT=2113
      - KURRENTDB_INSECURE=true
      - KURRENTDB_ENABLE_ATOM_PUB_OVER_HTTP=true
    ports:
      - "2113:2113"
    volumes:
      - kurrentdb-data:/var/lib/kurrentdb
      - kurrentdb-logs:/var/log/kurrentdb

volumes:
  kurrentdb-data:
  kurrentdb-logs:
```

### Connection Details
- **Connection String:** `kurrentdb://localhost:2113?tls=false`
- **Web UI:** http://localhost:2113
- **gRPC Port:** 2113

---

## .NET Client

### Installation

```bash
dotnet add package KurrentDB.Client
```

For persistent subscriptions:
```bash
dotnet add package KurrentDB.Client.PersistentSubscriptions
```

### Connection

```csharp
using KurrentDB.Client;

var settings = KurrentDBClientSettings.Create("kurrentdb://localhost:2113?tls=false");
await using var client = new KurrentDBClient(settings);
```

### Append Events

```csharp
using System.Text.Json;
using KurrentDB.Client;

// Define event
public record OrderCreated(string OrderId, string CustomerId, decimal Amount);

// Create and append
var evt = new OrderCreated(Guid.NewGuid().ToString(), "customer-123", 99.99m);

var eventData = new EventData(
    Uuid.NewUuid(),
    "OrderCreated",
    JsonSerializer.SerializeToUtf8Bytes(evt)
);

await client.AppendToStreamAsync(
    "order-123",
    StreamState.Any,
    new[] { eventData }
);
```

### Append with Optimistic Concurrency

```csharp
// Append only if stream doesn't exist
await client.AppendToStreamAsync(
    "order-123",
    StreamState.NoStream,
    new[] { eventData }
);

// Append at specific revision
await client.AppendToStreamAsync(
    "order-123",
    StreamRevision.FromInt64(expectedRevision),
    new[] { eventData }
);
```

### Multi-Stream Append

```csharp
// Append to multiple streams atomically
var metadata = JsonSerializer.SerializeToUtf8Bytes(new { TimeStamp = DateTime.UtcNow });

AppendStreamRequest[] requests = [
    new(
        "stream-one",
        StreamState.NoStream,
        [new EventData(Uuid.NewUuid(), "EventType", "data"u8.ToArray(), metadata)]
    ),
    new(
        "stream-two",
        StreamState.NoStream,
        [new EventData(Uuid.NewUuid(), "EventType", "data"u8.ToArray(), metadata)]
    )
];

await client.MultiStreamAppendAsync(requests);
```

### User Credentials Override

```csharp
// Override credentials for a specific operation
await client.AppendToStreamAsync(
    "some-stream",
    StreamState.Any,
    new[] { eventData },
    userCredentials: new UserCredentials("admin", "changeit")
);
```

### Read Events

```csharp
// Read forwards from start
var events = client.ReadStreamAsync(
    Direction.Forwards,
    "order-123",
    StreamPosition.Start
);

await foreach (var resolvedEvent in events)
{
    Console.WriteLine($"Event: {resolvedEvent.Event.EventType}");
    Console.WriteLine($"Data: {Encoding.UTF8.GetString(resolvedEvent.Event.Data.Span)}");
}

// Read with limit
var events = client.ReadStreamAsync(
    Direction.Forwards,
    "order-123",
    StreamPosition.Start,
    maxCount: 100
);

// Read backwards (latest first)
var events = client.ReadStreamAsync(
    Direction.Backwards,
    "order-123",
    StreamPosition.End
);
```

### Catch-up Subscription (Stream)

```csharp
await using var subscription = client.SubscribeToStream(
    "order-123",
    FromStream.Start
);

await foreach (var message in subscription.Messages)
{
    switch (message)
    {
        case StreamMessage.Event(var evnt):
            Console.WriteLine($"Received: {evnt.Event.EventType}");
            // Process event
            break;
        case StreamMessage.CaughtUp:
            Console.WriteLine("Caught up to live!");
            break;
    }
}
```

### Catch-up Subscription ($all)

```csharp
await using var subscription = client.SubscribeToAll(FromAll.Start);

await foreach (var message in subscription.Messages)
{
    switch (message)
    {
        case StreamMessage.Event(var evnt):
            Console.WriteLine($"Received: {evnt.Event.EventType}");
            break;
    }
}
```

### Catch-up Subscription with Checkpoint

```csharp
var checkpoint = FromStream.Start;  // Load from your storage

await using var subscription = client.SubscribeToStream("order-123", checkpoint);

await foreach (var message in subscription.Messages)
{
    switch (message)
    {
        case StreamMessage.Event(var evnt):
            // Process event
            await ProcessEventAsync(evnt);

            // Save checkpoint
            checkpoint = FromStream.After(evnt.OriginalEventNumber);
            await SaveCheckpointAsync(checkpoint);
            break;
    }
}
```

### Catch-up Subscription with Filter

```csharp
// Filter by stream prefix
var filterOptions = new SubscriptionFilterOptions(
    StreamFilter.Prefix("order-", "customer-")
);

await using var subscription = client.SubscribeToAll(
    FromAll.Start,
    filterOptions: filterOptions
);

// Filter by event type prefix
var filterOptions = new SubscriptionFilterOptions(
    EventTypeFilter.Prefix("Order")
);

// Filter by event type regex
var filterOptions = new SubscriptionFilterOptions(
    EventTypeFilter.RegularExpression("^user|^company")
);

// Filter by stream regex
var filterOptions = new SubscriptionFilterOptions(
    StreamFilter.RegularExpression("^account|^savings")
);

// Exclude system events
var filterOptions = new SubscriptionFilterOptions(
    EventTypeFilter.ExcludeSystemEvents()
);

// With checkpoint interval (checkpoints every 1000 events)
var filterOptions = new SubscriptionFilterOptions(
    EventTypeFilter.ExcludeSystemEvents(),
    checkpointInterval: 1000
);

await using var subscription = client.SubscribeToAll(FromAll.Start, filterOptions: filterOptions);
await foreach (var message in subscription.Messages)
{
    switch (message)
    {
        case StreamMessage.Event(var e):
            Console.WriteLine($"{e.Event.EventType} @ {e.Event.Position.PreparePosition}");
            break;
        case StreamMessage.AllStreamCheckpointReached(var p):
            Console.WriteLine($"Checkpoint at {p.PreparePosition}");
            // Save checkpoint to your storage
            break;
    }
}
```

### Persistent Subscription - Create

```csharp
using KurrentDB.Client;

await using var client = new KurrentDBPersistentSubscriptionsClient(
    KurrentDBClientSettings.Create("kurrentdb://localhost:2113?tls=false")
);

// Create subscription to stream
await client.CreateToStreamAsync(
    "order-123",
    "order-processor-group",
    new PersistentSubscriptionSettings(),
    userCredentials: new UserCredentials("admin", "changeit")
);

// Create subscription to $all
await client.CreateToAllAsync(
    "all-events-group",
    StreamFilter.Prefix("order-"),
    new PersistentSubscriptionSettings(),
    userCredentials: new UserCredentials("admin", "changeit")
);
```

### Persistent Subscription - Subscribe

```csharp
await using var subscription = client.SubscribeToStream(
    "order-123",
    "order-processor-group"
);

await foreach (var message in subscription.Messages)
{
    switch (message)
    {
        case PersistentSubscriptionMessage.Event(var evnt, var retryCount):
            try
            {
                await ProcessEventAsync(evnt);
                await subscription.Ack(evnt);
            }
            catch (Exception ex)
            {
                await subscription.Nack(
                    PersistentSubscriptionNakEventAction.Park,
                    ex.Message,
                    evnt
                );
            }
            break;
    }
}
```

### Persistent Subscription - Update

```csharp
var settings = new PersistentSubscriptionSettings(
    resolveLinkTos: true,
    checkPointLowerBound: 20
);

await client.UpdateToStreamAsync(
    "test-stream",
    "subscription-group",
    settings,
    userCredentials: new UserCredentials("admin", "changeit")
);
```

### Persistent Subscription - Delete

```csharp
await client.DeleteToStreamAsync(
    "test-stream",
    "subscription-group",
    userCredentials: new UserCredentials("admin", "changeit")
);

// Delete subscription to $all
await client.DeleteToAllAsync(
    "subscription-group",
    userCredentials: new UserCredentials("admin", "changeit")
);
```

### Persistent Subscription - Get Info

```csharp
// Get info for stream subscription
var info = await client.GetInfoToStreamAsync(
    "test-stream",
    "subscription-group",
    userCredentials: new UserCredentials("admin", "changeit")
);
Console.WriteLine($"GroupName: {info.GroupName}, Status: {info.Status}");

// Get info for $all subscription
var info = await client.GetInfoToAllAsync(
    "subscription-group",
    userCredentials: new UserCredentials("admin", "changeit")
);
```

### Persistent Subscription - List

```csharp
// List subscriptions to a stream
var subscriptions = await client.ListToStreamAsync(
    "test-stream",
    userCredentials: new UserCredentials("admin", "changeit")
);

foreach (var sub in subscriptions)
{
    Console.WriteLine($"GroupName: {sub.GroupName}, Status: {sub.Status}");
}

// List subscriptions to $all
var subscriptions = await client.ListToAllAsync(
    userCredentials: new UserCredentials("admin", "changeit")
);

// List all subscriptions
var subscriptions = await client.ListAllAsync(
    userCredentials: new UserCredentials("admin", "changeit")
);
```

### Persistent Subscription - Replay Parked Messages

```csharp
// Replay parked messages to stream
await client.ReplayParkedMessagesToStreamAsync(
    "test-stream",
    "subscription-group",
    stopAt: 10,
    userCredentials: new UserCredentials("admin", "changeit")
);

// Replay parked messages to $all
await client.ReplayParkedMessagesToAllAsync(
    "subscription-group",
    stopAt: 10,
    userCredentials: new UserCredentials("admin", "changeit")
);
```

### Persistent Subscription - Restart Subsystem

```csharp
await client.RestartSubsystemAsync(
    userCredentials: new UserCredentials("admin", "changeit")
);
```

---

## F# Client

F# uses the same `KurrentDB.Client` package as .NET with idiomatic F# patterns.

### Installation

```bash
dotnet add package KurrentDB.Client
```

For persistent subscriptions:
```bash
dotnet add package KurrentDB.Client.PersistentSubscriptions
```

### Connection

```fsharp
open KurrentDB.Client

let connectionString = "kurrentdb://localhost:2113?tls=false"
let settings = KurrentDBClientSettings.Create(connectionString)
use client = new KurrentDBClient(settings)
```

### Append Events

```fsharp
open System
open System.Text.Json
open KurrentDB.Client

type OrderCreated = {
    OrderId: string
    CustomerId: string
    Amount: decimal
}

let orderCreated = {
    OrderId = Guid.NewGuid().ToString("N")
    CustomerId = "customer-123"
    Amount = 99.99m
}

let eventData =
    EventData(
        Uuid.NewUuid(),
        "OrderCreated",
        JsonSerializer.SerializeToUtf8Bytes(orderCreated)
    )

// Append to stream
let! writeResult =
    client.AppendToStreamAsync(
        "order-123",
        StreamState.Any,
        [| eventData |]
    )
```

### Append with Optimistic Concurrency

```fsharp
// Only if stream doesn't exist
let! writeResult =
    client.AppendToStreamAsync(
        "order-123",
        StreamState.NoStream,
        [| eventData |]
    )

// At specific revision
let! writeResult =
    client.AppendToStreamAsync(
        "order-123",
        StreamRevision.FromInt64(5L),
        [| eventData |]
    )
```

### Read Events

```fsharp
open System.Text

// Read from stream
let events = client.ReadStreamAsync(Direction.Forwards, "order-123", StreamPosition.Start)

let rec readEvents () = task {
    let! hasNext = events.MoveNextAsync()
    if hasNext then
        let resolvedEvent = events.Current
        printfn "Event #%d: %s"
            (resolvedEvent.Event.EventNumber.ToInt64())
            resolvedEvent.Event.EventType
        printfn "Data: %s" (Encoding.UTF8.GetString(resolvedEvent.Event.Data.Span))
        return! readEvents()
}

// Read backwards
let events = client.ReadStreamAsync(
    Direction.Backwards,
    "order-123",
    StreamPosition.End,
    maxCount = 10L
)
```

### Catch-up Subscription (Stream)

```fsharp
open System.Threading

use subscription = client.SubscribeToStream("order-123", FromStream.Start)

let rec processMessages () = task {
    let! hasNext = subscription.Messages.MoveNextAsync(CancellationToken.None)
    if hasNext then
        match subscription.Messages.Current with
        | :? StreamMessage.Event as evtMsg ->
            let evnt = evtMsg.ResolvedEvent
            printfn "Received: %s @ %d" evnt.Event.EventType evnt.OriginalEventNumber
            // Process event
        | :? StreamMessage.CaughtUp ->
            printfn "Caught up to live!"
        | _ -> ()
        return! processMessages()
}
```

### Catch-up Subscription ($all)

```fsharp
use subscription = client.SubscribeToAll(FromAll.Start)

let rec processMessages () = task {
    let! hasNext = subscription.Messages.MoveNextAsync(CancellationToken.None)
    if hasNext then
        match subscription.Messages.Current with
        | :? StreamMessage.Event as evtMsg ->
            let evnt = evtMsg.ResolvedEvent
            printfn "Stream: %s, Type: %s" evnt.Event.StreamId evnt.Event.EventType
        | _ -> ()
        return! processMessages()
}
```

### Persistent Subscription - Create

```fsharp
open KurrentDB.Client

use psClient = new KurrentDBPersistentSubscriptionsClient(settings)

// Create subscription to stream
do! psClient.CreateToStreamAsync(
    "order-123",
    "order-processor-group",
    PersistentSubscriptionSettings(),
    userCredentials = UserCredentials("admin", "changeit")
)
```

### Persistent Subscription - Subscribe

```fsharp
use subscription = psClient.SubscribeToStream("order-123", "order-processor-group")

let rec processMessages () = task {
    let! hasNext = subscription.Messages.MoveNextAsync(CancellationToken.None)
    if hasNext then
        match subscription.Messages.Current with
        | :? PersistentSubscriptionMessage.Event as evtMsg ->
            try
                // Process event
                printfn "Processing: %s" evtMsg.ResolvedEvent.Event.EventType
                do! subscription.Ack(evtMsg.ResolvedEvent)
            with ex ->
                do! subscription.Nack(
                    PersistentSubscriptionNakEventAction.Park,
                    ex.Message,
                    evtMsg.ResolvedEvent
                )
        | _ -> ()
        return! processMessages()
}
```

---

## Java Client

### Installation (Maven)

```xml
<dependency>
    <groupId>com.eventstore</groupId>
    <artifactId>db-client-java</artifactId>
    <version>5.4.1</version>
</dependency>
```

### Installation (Gradle)

```groovy
implementation 'com.eventstore:db-client-java:5.4.1'
```

### Connection

```java
import com.eventstore.dbclient.*;

String connectionString = "esdb://localhost:2113?tls=false";
EventStoreDBClientSettings settings = EventStoreDBConnectionString.parseOrThrow(connectionString);
EventStoreDBClient client = EventStoreDBClient.create(settings);
```

### Append Events

```java
import com.eventstore.dbclient.*;
import com.fasterxml.jackson.databind.ObjectMapper;
import java.util.UUID;

// Define event
public record OrderCreated(String orderId, String customerId, double amount) {}

ObjectMapper mapper = new ObjectMapper();

// Create event
OrderCreated order = new OrderCreated(UUID.randomUUID().toString(), "customer-123", 99.99);
byte[] eventData = mapper.writeValueAsBytes(order);

EventData event = EventData.builderAsJson("OrderCreated", eventData).build();

// Append to stream
WriteResult writeResult = client.appendToStream("order-123", event).get();
System.out.println("Appended at revision: " + writeResult.getNextExpectedRevision());
```

### Append with Optimistic Concurrency

```java
import com.eventstore.dbclient.AppendToStreamOptions;
import com.eventstore.dbclient.ExpectedRevision;

// Only if stream doesn't exist
AppendToStreamOptions options = AppendToStreamOptions.get()
        .expectedRevision(ExpectedRevision.noStream());
client.appendToStream("order-123", options, event).get();

// At any revision
options = AppendToStreamOptions.get()
        .expectedRevision(ExpectedRevision.any());

// At specific revision
options = AppendToStreamOptions.get()
        .expectedRevision(ExpectedRevision.expectedRevision(5));
```

### Read Events

```java
import com.eventstore.dbclient.*;
import java.nio.charset.StandardCharsets;

// Read from stream
ReadStreamOptions readOptions = ReadStreamOptions.get()
        .forwards()
        .fromStart()
        .maxCount(100);

ReadResult result = client.readStream("order-123", readOptions).get();

for (ResolvedEvent resolvedEvent : result.getEvents()) {
    RecordedEvent recordedEvent = resolvedEvent.getOriginalEvent();
    System.out.println("Type: " + recordedEvent.getEventType());
    System.out.println("Data: " + new String(recordedEvent.getEventData(), StandardCharsets.UTF_8));
}

// Read backwards
readOptions = ReadStreamOptions.get()
        .backwards()
        .fromEnd()
        .maxCount(10);
```

### Catch-up Subscription (Stream)

```java
import com.eventstore.dbclient.*;

SubscribeToStreamOptions subscribeOptions = SubscribeToStreamOptions.get()
        .fromStart()
        .resolveLinkTos();

Subscription subscription = client.subscribeToStream("order-123", new SubscriptionListener() {
    @Override
    public void onEvent(Subscription subscription, ResolvedEvent event) {
        RecordedEvent recordedEvent = event.getOriginalEvent();
        System.out.println("Received: " + recordedEvent.getEventType() +
                " @ revision " + recordedEvent.getRevision());
        // Process event
    }

    @Override
    public void onCancelled(Subscription subscription, Throwable exception) {
        if (exception != null) {
            System.out.println("Subscription cancelled: " + exception.getMessage());
        }
    }
}, subscribeOptions).get();

// Later: stop subscription
subscription.stop();
```

### Catch-up Subscription ($all)

```java
SubscribeToAllOptions allOptions = SubscribeToAllOptions.get()
        .fromStart()
        .resolveLinkTos();

Subscription subscription = client.subscribeToAll(new SubscriptionListener() {
    @Override
    public void onEvent(Subscription subscription, ResolvedEvent event) {
        RecordedEvent recordedEvent = event.getOriginalEvent();
        System.out.println("Stream: " + recordedEvent.getStreamId());
        System.out.println("Type: " + recordedEvent.getEventType());
    }

    @Override
    public void onCancelled(Subscription subscription, Throwable exception) {
        // Handle cancellation
    }
}, allOptions).get();
```

### Persistent Subscription - Create

```java
import com.eventstore.dbclient.*;

EventStoreDBPersistentSubscriptionsClient psClient =
    EventStoreDBPersistentSubscriptionsClient.from(client);

// Create subscription to stream
CreatePersistentSubscriptionToStreamOptions options =
    CreatePersistentSubscriptionToStreamOptions.get()
        .fromStart()
        .resolveLinkTos();

psClient.createToStream("order-123", "order-processor-group", options).get();
```

### Persistent Subscription - Subscribe

```java
PersistentSubscription subscription = psClient.subscribeToStream(
        "order-123",
        "order-processor-group",
        new PersistentSubscriptionListener() {
            @Override
            public void onEvent(PersistentSubscription subscription, int retryCount, ResolvedEvent event) {
                RecordedEvent recordedEvent = event.getOriginalEvent();
                System.out.println("Processing: " + recordedEvent.getEventType());

                try {
                    // Process event
                    // ... your business logic ...

                    // Acknowledge success
                    subscription.ack(event);
                } catch (Exception e) {
                    // Park failed event
                    subscription.nack(NackAction.Park, e.getMessage(), event);
                }
            }

            @Override
            public void onCancelled(PersistentSubscription subscription, Throwable exception) {
                if (exception != null) {
                    System.out.println("Subscription cancelled: " + exception.getMessage());
                }
            }
        }
).get();
```

---

## Python Client

### Installation

```bash
pip install kurrentdbclient
```

### Connection

```python
from kurrentdbclient import KurrentDBClient

# Insecure connection
client = KurrentDBClient(uri="kurrentdb://localhost:2113?tls=false")

# With authentication
client = KurrentDBClient(uri="kurrentdb://admin:changeit@localhost:2113?tls=false")
```

### Append Events

```python
from kurrentdbclient import KurrentDBClient, NewEvent, StreamState
import json
import uuid

client = KurrentDBClient(uri="kurrentdb://localhost:2113?tls=false")

# Create event
event = NewEvent(
    type="OrderCreated",
    data=json.dumps({
        "order_id": str(uuid.uuid4()),
        "customer_id": "customer-123",
        "amount": 99.99
    }).encode('utf-8'),
    content_type="application/json"
)

# Append to stream
commit_position = client.append_to_stream(
    stream_name="order-123",
    current_version=StreamState.ANY,
    events=[event]
)
```

### Append with Optimistic Concurrency

```python
# Only if stream doesn't exist
client.append_to_stream(
    stream_name="order-123",
    current_version=StreamState.NO_STREAM,
    events=[event]
)

# At specific version
client.append_to_stream(
    stream_name="order-123",
    current_version=5,  # Expected current version
    events=[event]
)
```

### Read Events

```python
# Read from stream
events = client.get_stream(stream_name="order-123")

for event in events:
    print(f"Type: {event.type}")
    print(f"Data: {event.data.decode('utf-8')}")
    print(f"Position: {event.stream_position}")

# Read with options
events = client.get_stream(
    stream_name="order-123",
    stream_position=0,  # Start position
    limit=100,          # Max events
    backwards=False     # Direction
)

# Read backwards
events = client.get_stream(
    stream_name="order-123",
    backwards=True
)
```

### Catch-up Subscription (Stream)

```python
# Subscribe to stream from beginning
subscription = client.subscribe_to_stream(stream_name="order-123")

for event in subscription:
    print(f"Received: {event.type}")
    # Process event

    # Stop condition (optional)
    if should_stop():
        break

# Subscribe from specific position
subscription = client.subscribe_to_stream(
    stream_name="order-123",
    stream_position=10  # Start after position 10
)

# Subscribe from end (new events only)
subscription = client.subscribe_to_stream(
    stream_name="order-123",
    from_end=True
)
```

### Catch-up Subscription ($all)

```python
# Subscribe to all events
subscription = client.subscribe_to_all()

for event in subscription:
    print(f"Stream: {event.stream_name}")
    print(f"Type: {event.type}")
    # Process event

# Subscribe from specific commit position
subscription = client.subscribe_to_all(commit_position=12345)

# Subscribe with filter
subscription = client.subscribe_to_all(
    filter_include=[r"^order-"],  # Regex for stream names
    filter_exclude=[r"^\$"]       # Exclude system streams
)
```

### Persistent Subscription - Create

```python
# Create persistent subscription to $all
client.create_subscription_to_all(
    group_name="order-processor",
    filter_include=[r"^order-"],
    consumer_strategy="RoundRobin"
)

# Create persistent subscription to stream
client.create_subscription_to_stream(
    group_name="order-processor",
    stream_name="order-123"
)
```

### Persistent Subscription - Subscribe

```python
# Read from persistent subscription
subscription = client.read_subscription_to_all(group_name="order-processor")

for event in subscription:
    try:
        # Process event
        print(f"Processing: {event.type}")

        # Acknowledge success
        subscription.ack(event.ack_id)
    except Exception as e:
        # Negative acknowledge - park for retry
        subscription.nack(event.ack_id, action="park")
```

---

## Node.js Client

### Installation

```bash
npm install @kurrent/kurrentdb-client
# or
yarn add @kurrent/kurrentdb-client
```

### Connection

```typescript
import { KurrentDBClient } from "@kurrent/kurrentdb-client";

// Insecure connection
const client = KurrentDBClient.connectionString`kurrentdb://localhost:2113?tls=false`;

// With authentication
const client = KurrentDBClient.connectionString`kurrentdb://admin:changeit@localhost:2113?tls=false`;
```

### Append Events

```typescript
import { KurrentDBClient, jsonEvent } from "@kurrent/kurrentdb-client";
import { v4 as uuid } from "uuid";

const client = KurrentDBClient.connectionString`kurrentdb://localhost:2113?tls=false`;

// Create event
const event = jsonEvent({
    type: "OrderCreated",
    data: {
        orderId: uuid(),
        customerId: "customer-123",
        amount: 99.99
    }
});

// Append to stream
await client.appendToStream("order-123", event);
```

### Append with Optimistic Concurrency

```typescript
import { NO_STREAM, ANY, StreamState } from "@kurrent/kurrentdb-client";

// Only if stream doesn't exist
await client.appendToStream("order-123", event, {
    expectedRevision: NO_STREAM
});

// At any revision
await client.appendToStream("order-123", event, {
    expectedRevision: ANY
});

// At specific revision
await client.appendToStream("order-123", event, {
    expectedRevision: BigInt(5)
});
```

### Read Events

```typescript
import { FORWARDS, BACKWARDS, START, END } from "@kurrent/kurrentdb-client";

// Read forwards from start
const events = client.readStream("order-123", {
    direction: FORWARDS,
    fromRevision: START,
    maxCount: 100
});

for await (const resolvedEvent of events) {
    console.log(`Type: ${resolvedEvent.event?.type}`);
    console.log(`Data: ${JSON.stringify(resolvedEvent.event?.data)}`);
}

// Read backwards from end
const events = client.readStream("order-123", {
    direction: BACKWARDS,
    fromRevision: END,
    maxCount: 10
});
```

### Catch-up Subscription (Stream)

```typescript
import { START } from "@kurrent/kurrentdb-client";

// Subscribe from start
const subscription = client.subscribeToStream("order-123", {
    fromRevision: START
});

for await (const resolvedEvent of subscription) {
    console.log(`Received: ${resolvedEvent.event?.type}`);
    // Process event
}

// Subscribe from specific revision
const subscription = client.subscribeToStream("order-123", {
    fromRevision: BigInt(10)
});

// Subscribe from end (new events only)
const subscription = client.subscribeToStream("order-123", {
    fromRevision: END
});
```

### Catch-up Subscription ($all)

```typescript
import { START, streamNameFilter, eventTypeFilter } from "@kurrent/kurrentdb-client";

// Subscribe to all
const subscription = client.subscribeToAll({
    fromPosition: START
});

for await (const resolvedEvent of subscription) {
    console.log(`Stream: ${resolvedEvent.event?.streamId}`);
    console.log(`Type: ${resolvedEvent.event?.type}`);
}

// Subscribe with stream filter
const subscription = client.subscribeToAll({
    fromPosition: START,
    filter: streamNameFilter({ prefixes: ["order-", "customer-"] })
});

// Subscribe with event type filter
const subscription = client.subscribeToAll({
    fromPosition: START,
    filter: eventTypeFilter({ prefixes: ["Order"] })
});
```

### Persistent Subscription - Create

```typescript
import {
    persistentSubscriptionToStreamSettingsFromDefaults,
    persistentSubscriptionToAllSettingsFromDefaults,
    streamNameFilter
} from "@kurrent/kurrentdb-client";

// Create subscription to stream
await client.createPersistentSubscriptionToStream(
    "order-123",
    "order-processor-group",
    persistentSubscriptionToStreamSettingsFromDefaults()
);

// Create subscription to $all with filter
await client.createPersistentSubscriptionToAll(
    "all-orders-group",
    persistentSubscriptionToAllSettingsFromDefaults(),
    {
        filter: streamNameFilter({ prefixes: ["order-"] })
    }
);
```

### Persistent Subscription - Subscribe

```typescript
import { PARK } from "@kurrent/kurrentdb-client";

const subscription = client.subscribeToPersistentSubscriptionToStream(
    "order-123",
    "order-processor-group"
);

try {
    for await (const event of subscription) {
        try {
            console.log(`Processing: ${event.event?.type}`);
            // Process event

            await subscription.ack(event);
        } catch (error) {
            await subscription.nack(PARK, error.toString(), event);
        }
    }
} catch (error) {
    console.log(`Subscription dropped: ${error}`);
}
```

---

## Go Client

### Installation

```bash
go get github.com/kurrent-io/KurrentDB-Client-Go/kurrentdb
```

### Important Notes

| Requirement | Details |
|-------------|---------|
| **Go Version** | Requires Go 1.23+ |
| **ContentType** | Use `kurrentdb.ContentTypeJson` (not `JsonContentType`) |
| **Error Handling** | Use `kurrentdb.FromError(err)` and check `.Code()` against `kurrentdb.ErrorCodeResourceNotFound` |
| **Default Options** | Use empty structs for defaults: `kurrentdb.AppendToStreamOptions{}` |

### Error Handling Pattern

```go
if err, ok := kurrentdb.FromError(err); !ok {
    if err.Code() == kurrentdb.ErrorCodeResourceNotFound {
        fmt.Println("Stream not found")
    } else {
        panic(err)
    }
}
```

### Connection

```go
package main

import (
    "github.com/kurrent-io/KurrentDB-Client-Go/kurrentdb"
)

func main() {
    settings, err := kurrentdb.ParseConnectionString("kurrentdb://localhost:2113?tls=false")
    if err != nil {
        panic(err)
    }

    client, err := kurrentdb.NewClient(settings)
    if err != nil {
        panic(err)
    }
    defer client.Close()
}
```

### Append Events

```go
package main

import (
    "context"
    "encoding/json"
    "github.com/google/uuid"
    "github.com/kurrent-io/KurrentDB-Client-Go/kurrentdb"
)

type OrderCreated struct {
    OrderId    string  `json:"orderId"`
    CustomerId string  `json:"customerId"`
    Amount     float64 `json:"amount"`
}

func main() {
    settings, _ := kurrentdb.ParseConnectionString("kurrentdb://localhost:2113?tls=false")
    client, _ := kurrentdb.NewClient(settings)
    defer client.Close()

    // Create event
    order := OrderCreated{
        OrderId:    uuid.New().String(),
        CustomerId: "customer-123",
        Amount:     99.99,
    }

    data, _ := json.Marshal(order)

    eventData := kurrentdb.EventData{
        EventID:     uuid.New(),
        ContentType: kurrentdb.ContentTypeJson,
        EventType:   "OrderCreated",
        Data:        data,
    }

    // Append to stream
    _, err := client.AppendToStream(
        context.Background(),
        "order-123",
        kurrentdb.AppendToStreamOptions{},
        eventData,
    )
    if err != nil {
        panic(err)
    }
}
```

### Append with Optimistic Concurrency

```go
// Only if stream doesn't exist
opts := kurrentdb.AppendToStreamOptions{
    ExpectedRevision: kurrentdb.NoStream{},
}
_, err := client.AppendToStream(ctx, "order-123", opts, eventData)

// At any revision
opts := kurrentdb.AppendToStreamOptions{
    ExpectedRevision: kurrentdb.Any{},
}

// At specific revision
opts := kurrentdb.AppendToStreamOptions{
    ExpectedRevision: kurrentdb.Revision(5),
}
```

### Multi-Stream Append

```go
type OrderCreated struct {
    OrderId string  `json:"orderId"`
    Amount  float64 `json:"amount"`
}

type PaymentProcessed struct {
    PaymentId string  `json:"paymentId"`
    Amount    float64 `json:"amount"`
}

metadata := map[string]interface{}{"source": "web-store"}
metadataBytes, _ := json.Marshal(metadata)

orderData, _ := json.Marshal(OrderCreated{OrderId: "12345", Amount: 99.99})
paymentData, _ := json.Marshal(PaymentProcessed{PaymentId: "PAY-789", Amount: 99.99})

requests := []kurrentdb.AppendStreamRequest{
    {
        StreamName: "order-stream-1",
        Events: slices.Values([]kurrentdb.EventData{{
            EventID:     uuid.New(),
            EventType:   "OrderCreated",
            ContentType: kurrentdb.ContentTypeJson,
            Data:        orderData,
            Metadata:    metadataBytes,
        }}),
        ExpectedStreamState: kurrentdb.Any{},
    },
    {
        StreamName: "payment-stream-1",
        Events: slices.Values([]kurrentdb.EventData{{
            EventID:     uuid.New(),
            EventType:   "PaymentProcessed",
            ContentType: kurrentdb.ContentTypeJson,
            Data:        paymentData,
            Metadata:    metadataBytes,
        }}),
        ExpectedStreamState: kurrentdb.Any{},
    },
}

_, err := client.MultiStreamAppend(context.Background(), slices.Values(requests))
if err != nil {
    var streamRevisionConflictErr *kurrentdb.StreamRevisionConflictError
    if errors.As(err, &streamRevisionConflictErr) {
        log.Printf("Stream revision conflict on stream %s", streamRevisionConflictErr.Stream)
    }
}
```

### User Credentials Override

```go
credentials := &kurrentdb.Credentials{Login: "admin", Password: "changeit"}

_, err := client.AppendToStream(ctx, "some-stream", kurrentdb.AppendToStreamOptions{
    Authenticated: credentials,
}, eventData)
```

### Read Events

```go
import (
    "context"
    "io"
)

// Read from stream
stream, err := client.ReadStream(
    context.Background(),
    "order-123",
    kurrentdb.ReadStreamOptions{
        Direction: kurrentdb.Forwards,
        From:      kurrentdb.Start{},
    },
    100, // max count
)
if err != nil {
    panic(err)
}
defer stream.Close()

for {
    event, err := stream.Recv()
    if err == io.EOF {
        break
    }
    if err != nil {
        panic(err)
    }

    fmt.Printf("Type: %s\n", event.Event.EventType)
    fmt.Printf("Data: %s\n", string(event.Event.Data))
}

// Read backwards
stream, _ := client.ReadStream(ctx, "order-123", kurrentdb.ReadStreamOptions{
    Direction: kurrentdb.Backwards,
    From:      kurrentdb.End{},
}, 10)
```

### Catch-up Subscription (Stream)

```go
// Subscribe to stream
subscription, err := client.SubscribeToStream(
    context.Background(),
    "order-123",
    kurrentdb.SubscribeToStreamOptions{
        From: kurrentdb.Start{},
    },
)
if err != nil {
    panic(err)
}
defer subscription.Close()

for {
    event := subscription.Recv()

    if event.EventAppeared != nil {
        fmt.Printf("Received: %s\n", event.EventAppeared.Event.EventType)
        // Process event
    }

    if event.SubscriptionDropped != nil {
        fmt.Printf("Subscription dropped: %v\n", event.SubscriptionDropped.Error)
        break
    }
}
```

### Catch-up Subscription ($all)

```go
// Subscribe to $all
subscription, err := client.SubscribeToAll(
    context.Background(),
    kurrentdb.SubscribeToAllOptions{
        From: kurrentdb.Start{},
    },
)

for {
    event := subscription.Recv()

    if event.EventAppeared != nil {
        fmt.Printf("Stream: %s\n", event.EventAppeared.Event.StreamID)
        fmt.Printf("Type: %s\n", event.EventAppeared.Event.EventType)
    }

    if event.SubscriptionDropped != nil {
        break
    }
}
```

### Server-Side Filtering

```go
// Exclude system events
sub, _ := client.SubscribeToAll(ctx, kurrentdb.SubscribeToAllOptions{
    Filter: kurrentdb.ExcludeSystemEventsFilter(),
})

// Filter by event type prefix
sub, _ := client.SubscribeToAll(ctx, kurrentdb.SubscribeToAllOptions{
    Filter: &kurrentdb.SubscriptionFilter{
        Type:     kurrentdb.EventFilterType,
        Prefixes: []string{"customer-"},
    },
})

// Filter by event type regex
sub, _ := client.SubscribeToAll(ctx, kurrentdb.SubscribeToAllOptions{
    Filter: &kurrentdb.SubscriptionFilter{
        Type:  kurrentdb.EventFilterType,
        Regex: "^user|^company",
    },
})

// Filter by stream prefix
sub, _ := client.SubscribeToAll(ctx, kurrentdb.SubscribeToAllOptions{
    Filter: &kurrentdb.SubscriptionFilter{
        Type:     kurrentdb.StreamFilterType,
        Prefixes: []string{"user-"},
    },
})

// Filter by stream regex
sub, _ := client.SubscribeToAll(ctx, kurrentdb.SubscribeToAllOptions{
    Filter: &kurrentdb.SubscriptionFilter{
        Type:  kurrentdb.StreamFilterType,
        Regex: "^user|^company",
    },
})

// Handle checkpoints
for {
    event := sub.Recv()

    if event.EventAppeared != nil {
        fmt.Printf("Event: %s\n", event.EventAppeared.Event.EventType)
    }

    if event.CheckPointReached != nil {
        // Save checkpoint to your storage
        fmt.Printf("Checkpoint at commit position: %d\n", event.CheckPointReached.Commit)
    }

    if event.SubscriptionDropped != nil {
        break
    }
}
```

### Persistent Subscription - Create

```go
// Create subscription to stream
err := client.CreatePersistentSubscription(
    context.Background(),
    "order-123",
    "order-processor-group",
    kurrentdb.PersistentStreamSubscriptionOptions{},
)
if err != nil {
    panic(err)
}

// Create subscription to $all
err := client.CreatePersistentSubscriptionToAll(
    context.Background(),
    "all-events-group",
    kurrentdb.PersistentAllSubscriptionOptions{
        Filter: &kurrentdb.SubscriptionFilter{
            Type:     kurrentdb.StreamFilterType,
            Prefixes: []string{"order-"},
        },
    },
)
```

### Persistent Subscription - Subscribe

```go
// Subscribe to persistent subscription
subscription, err := client.SubscribeToPersistentSubscription(
    context.Background(),
    "order-123",
    "order-processor-group",
    kurrentdb.SubscribeToPersistentSubscriptionOptions{},
)
if err != nil {
    panic(err)
}
defer subscription.Close()

for {
    event := subscription.Recv()

    if event.EventAppeared != nil {
        // Process event
        fmt.Printf("Processing: %s\n", event.EventAppeared.Event.EventType)

        // Acknowledge
        err := subscription.Ack(event.EventAppeared.Event)
        if err != nil {
            // Negative acknowledge - park
            subscription.Nack("Processing failed", kurrentdb.NackActionPark, event.EventAppeared.Event)
        }
    }

    if event.SubscriptionDropped != nil {
        break
    }
}
```

### Persistent Subscription - Update

```go
options := kurrentdb.PersistentStreamSubscriptionOptions{
    Settings: &kurrentdb.PersistentSubscriptionSettings{
        ResolveLinkTos:       true,
        CheckpointLowerBound: 20,
    },
}

err := client.UpdatePersistentSubscription(ctx, "test-stream", "subscription-group", options)
```

### Persistent Subscription - Delete

```go
// Delete subscription to stream
err := client.DeletePersistentSubscription(ctx, "test-stream", "subscription-group", kurrentdb.DeletePersistentSubscriptionOptions{})

// Delete subscription to $all
err := client.DeletePersistentSubscriptionToAll(ctx, "subscription-group", kurrentdb.DeletePersistentSubscriptionOptions{})
```

### Persistent Subscription - Get Info

```go
// Get info for stream subscription
info, err := client.GetPersistentSubscriptionInfo(ctx, "test-stream", "subscription-group", kurrentdb.GetPersistentSubscriptionOptions{})
log.Printf("GroupName: %s, Status: %s", info.GroupName, info.Status)

// Get info for $all subscription
info, err := client.GetPersistentSubscriptionInfoToAll(ctx, "subscription-group", kurrentdb.GetPersistentSubscriptionOptions{})
```

### Persistent Subscription - List

```go
// List subscriptions to a stream
subs, err := client.ListPersistentSubscriptionsForStream(ctx, "test-stream", kurrentdb.ListPersistentSubscriptionsOptions{})
for _, sub := range subs {
    log.Printf("GroupName: %s, Status: %s", sub.GroupName, sub.Status)
}

// List subscriptions to $all
subs, err := client.ListPersistentSubscriptionsToAll(ctx, kurrentdb.ListPersistentSubscriptionsOptions{})
```

### Persistent Subscription - Replay Parked Messages

```go
// Replay parked messages to stream
err := client.ReplayParkedMessages(ctx, "test-stream", "subscription-group", kurrentdb.ReplayParkedMessagesOptions{
    StopAt: 10,
})

// Replay parked messages to $all
err := client.ReplayParkedMessagesToAll(ctx, "subscription-group", kurrentdb.ReplayParkedMessagesOptions{
    StopAt: 10,
})
```

### Persistent Subscription - Restart Subsystem

```go
err := client.RestartPersistentSubscriptionSubsystem(ctx, kurrentdb.RestartPersistentSubscriptionSubsystemOptions{})
```

---

## Rust Client

### Installation (Cargo.toml)

```toml
[package]
edition = "2024"  # Required for kurrentdb v1.0

[dependencies]
kurrentdb = "1.0"
serde = { version = "1.0", features = ["derive"] }
serde_json = "1.0"
tokio = { version = "1.0", features = ["full"] }
uuid = { version = "1.0", features = ["v4"] }
futures = "0.3"
```

### Important Notes

| Requirement | Details |
|-------------|---------|
| **Rust Edition** | Requires `edition = "2024"` in Cargo.toml (Rust 1.85+) |
| **Docker Base** | Use `rust:1.85-slim` for containers |
| **Build Dependencies** | Needs `pkg-config`, `libssl-dev`, `protobuf-compiler` |
| **Error Handling** | Match `kurrentdb::Error::ResourceNotFound` for stream not found |
| **Stream Iteration** | Use `while let Ok(Some(event)) = stream.next().await` pattern |
| **Original Event** | Access via `event.get_original_event()` returns `RecordedEvent` |

### Error Handling Pattern

```rust
use kurrentdb::Error;

match client.read_stream(stream_name, &options).await {
    Ok(stream) => { /* process events */ }
    Err(Error::ResourceNotFound) => {
        println!("Stream not found");
    }
    Err(e) => return Err(e.into()),
}
```

### Connection

```rust
use kurrentdb::Client;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let settings = "kurrentdb://localhost:2113?tls=false".parse()?;
    let client = Client::new(settings)?;

    Ok(())
}
```

### Append Events

```rust
use kurrentdb::{Client, EventData};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Serialize, Deserialize)]
struct OrderCreated {
    order_id: String,
    customer_id: String,
    amount: f64,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let settings = "kurrentdb://localhost:2113?tls=false".parse()?;
    let client = Client::new(settings)?;

    // Create event
    let order = OrderCreated {
        order_id: Uuid::new_v4().to_string(),
        customer_id: "customer-123".to_string(),
        amount: 99.99,
    };

    let event = EventData::json("OrderCreated", &order)?
        .id(Uuid::new_v4());

    // Append to stream
    client
        .append_to_stream("order-123", &Default::default(), event)
        .await?;

    Ok(())
}
```

### Append with Optimistic Concurrency

```rust
use kurrentdb::{AppendToStreamOptions, ExpectedRevision};

// Only if stream doesn't exist
let options = AppendToStreamOptions::default()
    .expected_revision(ExpectedRevision::NoStream);

client.append_to_stream("order-123", &options, event).await?;

// At any revision
let options = AppendToStreamOptions::default()
    .expected_revision(ExpectedRevision::Any);

// At specific revision
let options = AppendToStreamOptions::default()
    .expected_revision(ExpectedRevision::Exact(5));
```

### Read Events

```rust
use kurrentdb::{ReadStreamOptions, StreamPosition};
use futures::StreamExt;

// Read from stream
let options = ReadStreamOptions::default()
    .position(StreamPosition::Start)
    .max_count(100);

let mut stream = client.read_stream("order-123", &options).await?;

while let Some(event) = stream.next().await? {
    println!("Type: {}", event.get_original_event().event_type);

    let data: OrderCreated = event.get_original_event().as_json()?;
    println!("Data: {:?}", data);
}

// Read backwards
let options = ReadStreamOptions::default()
    .position(StreamPosition::End)
    .backwards()
    .max_count(10);
```

### Catch-up Subscription (Stream)

```rust
use kurrentdb::SubscribeToStreamOptions;
use futures::StreamExt;

// Subscribe to stream
let options = SubscribeToStreamOptions::default()
    .start_from(StreamPosition::Start);

let mut subscription = client
    .subscribe_to_stream("order-123", &options)
    .await?;

while let Some(event) = subscription.next().await? {
    println!("Received: {}", event.get_original_event().event_type);
    // Process event
}
```

### Catch-up Subscription ($all)

```rust
use kurrentdb::{SubscribeToAllOptions, SubscriptionFilter};
use futures::StreamExt;

// Subscribe to $all
let mut subscription = client
    .subscribe_to_all(&Default::default())
    .await?;

while let Some(event) = subscription.next().await? {
    println!("Stream: {}", event.get_original_event().stream_id);
    println!("Type: {}", event.get_original_event().event_type);
}

// Subscribe with filter
let filter = SubscriptionFilter::on_stream_name()
    .add_prefix("order-");

let options = SubscribeToAllOptions::default()
    .filter(filter);

let mut subscription = client.subscribe_to_all(&options).await?;
```

### Server-Side Filtering

```rust
use kurrentdb::{SubscribeToAllOptions, SubscriptionFilter, SubscriptionEvent};

// Exclude system events
let filter = SubscriptionFilter::on_event_type().exclude_system_events();
let options = SubscribeToAllOptions::default().filter(filter);
let mut sub = client.subscribe_to_all(&options).await;

// Filter by event type prefix
let filter = SubscriptionFilter::on_event_type().add_prefix("customer-");
let options = SubscribeToAllOptions::default().filter(filter);

// Filter by event type regex
let filter = SubscriptionFilter::on_event_type().regex("^user|^company");
let options = SubscribeToAllOptions::default().filter(filter);

// Filter by stream name prefix
let filter = SubscriptionFilter::on_stream_name().add_prefix("user-");
let options = SubscribeToAllOptions::default().filter(filter);

// Filter by stream name regex
let filter = SubscriptionFilter::on_stream_name().regex("^account|^savings");
let options = SubscribeToAllOptions::default().filter(filter);

// Handle checkpoints
loop {
    let event = sub.next_subscription_event().await?;
    match event {
        SubscriptionEvent::EventAppeared(event) => {
            let stream_id = event.get_original_stream_id();
            let revision = event.get_original_event().revision;
            println!("Received event {}@{}", revision, stream_id);
        }
        SubscriptionEvent::Checkpoint(position) => {
            // Save checkpoint to your storage
            println!("Checkpoint at commit position {}", position.commit);
        }
        _ => {}
    }
}
```

### Persistent Subscription - Create

```rust
use kurrentdb::{
    PersistentSubscriptionOptions,
    PersistentSubscriptionToAllOptions,
    SubscriptionFilter,
};

// Create subscription to stream
client
    .create_persistent_subscription("order-123", "order-processor-group", &Default::default())
    .await?;

// Create subscription to $all with filter
let filter = SubscriptionFilter::on_stream_name().add_prefix("order-");

let options = PersistentSubscriptionToAllOptions::default()
    .filter(filter);

client
    .create_persistent_subscription_to_all("all-orders-group", &options)
    .await?;
```

### Persistent Subscription - Subscribe

```rust
use kurrentdb::NakAction;

// Subscribe to persistent subscription
let mut subscription = client
    .subscribe_to_persistent_subscription(
        "order-123",
        "order-processor-group",
        &Default::default(),
    )
    .await?;

loop {
    match subscription.next().await {
        Ok(event) => {
            println!("Processing: {}", event.get_original_event().event_type);

            // Acknowledge
            if let Err(e) = subscription.ack(&event).await {
                // Negative acknowledge - park
                subscription.nack(&event, NakAction::Park).await?;
            }
        }
        Err(e) => {
            println!("Error: {}", e);
            break;
        }
    }
}
```

### Persistent Subscription - Update

```rust
use kurrentdb::PersistentSubscriptionOptions;

let options = PersistentSubscriptionOptions::default()
    .resolve_link_tos(true)
    .checkpoint_lower_bound(20);

client
    .update_persistent_subscription("test-stream", "subscription-group", &options)
    .await?;
```

### Persistent Subscription - Delete

```rust
// Delete subscription to stream
client
    .delete_persistent_subscription("test-stream", "subscription-group", &Default::default())
    .await?;

// Delete subscription to $all
client
    .delete_persistent_subscription_to_all("subscription-group", &Default::default())
    .await?;
```

### Persistent Subscription - Get Info

```rust
// Get info for stream subscription
let info = client
    .get_persistent_subscription_info("test-stream", "subscription-group", &Default::default())
    .await?;
println!("GroupName: {}, Status: {:?}", info.group_name, info.status);

// Get info for $all subscription
let info = client
    .get_persistent_subscription_info_to_all("subscription-group", &Default::default())
    .await?;
```

### Persistent Subscription - List

```rust
// List subscriptions to a stream
let subscriptions = client
    .list_persistent_subscriptions_for_stream("test-stream", &Default::default())
    .await?;
for s in subscriptions {
    println!("GroupName: {}, Status: {:?}", s.group_name, s.status);
}

// List subscriptions to $all
let subscriptions = client
    .list_persistent_subscriptions_to_all(&Default::default())
    .await?;

// List all subscriptions
let subscriptions = client
    .list_all_persistent_subscriptions(&Default::default())
    .await?;
```

### Persistent Subscription - Replay Parked Messages

```rust
use kurrentdb::ReplayParkedMessagesOptions;

// Replay parked messages to stream
let options = ReplayParkedMessagesOptions::default().stop_at(10);
client
    .replay_parked_messages("test-stream", "subscription-group", &options)
    .await?;

// Replay parked messages to $all
client
    .replay_parked_messages_to_all("subscription-group", &options)
    .await?;
```

### Persistent Subscription - Restart Subsystem

```rust
client
    .restart_persistent_subscription_subsystem(&Default::default())
    .await?;
```


---

## Circuit Breaker Pattern

The Circuit Breaker pattern (https://martinfowler.com/bliki/CircuitBreaker.html) protects against cascading failures when processing events from persistent subscriptions.

### States

| State | Description |
|-------|-------------|
| **CLOSED** | Normal operation - events are processed |
| **OPEN** | Circuit tripped - events are parked/nacked |
| **HALF_OPEN** | Testing recovery - limited event processing |

### Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `failureThreshold` | 5 | Consecutive failures before opening |
| `successThreshold` | 3 | Successes needed to close from half-open |
| `timeout` | 30s | Time before attempting half-open |
| `halfOpenMaxCalls` | 3 | Max concurrent calls in half-open |

### Implementation Pattern

```
1. Check circuit state before processing
2. If OPEN and timeout elapsed, transition to HALF_OPEN
3. Process event within circuit breaker
4. On success: record_success() - may close circuit
5. On failure: record_failure() - may open circuit
6. When circuit OPEN: nack/park events
```

---

## Connection String Parameters

All clients support these connection string parameters:

| Parameter | Values | Default | Description |
|-----------|--------|---------|-------------|
| `tls` | true/false | true | Enable TLS encryption |
| `tlsVerifyCert` | true/false | true | Verify TLS certificate |
| `connectionName` | string | - | Connection identifier |
| `nodePreference` | leader/follower/random | leader | Preferred node type |
| `maxDiscoverAttempts` | number | 10 | Max cluster discovery attempts |
| `discoveryInterval` | ms | 100 | Time between discovery attempts |
| `gossipTimeout` | ms | 5000 | Gossip protocol timeout |
| `keepAliveInterval` | ms | 10000 | Keep-alive ping interval |
| `keepAliveTimeout` | ms | 10000 | Keep-alive response timeout |

## Nack Actions

When negatively acknowledging events in persistent subscriptions:

| Action | Description |
|--------|-------------|
| `Park` | Move to parked queue for manual inspection |
| `Retry` | Retry processing immediately |
| `Skip` | Skip this event and continue |
| `Stop` | Stop the subscription |
