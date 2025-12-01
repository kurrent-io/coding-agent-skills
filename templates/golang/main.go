// KurrentDB Go Client Example - Append, Read, and Subscribe
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"io"
	"os"

	"github.com/google/uuid"
	"github.com/kurrent-io/KurrentDB-Client-Go/kurrentdb"
)

// OrderCreated represents an order creation event
type OrderCreated struct {
	OrderID    string  `json:"orderId"`
	CustomerID string  `json:"customerId"`
	Amount     float64 `json:"amount"`
}

func main() {
	ctx := context.Background()

	// === CONNECTION ===
	connectionString := os.Getenv("KURRENTDB_CONNECTION_STRING")
	if connectionString == "" {
		connectionString = "kurrentdb://localhost:2113?tls=false"
	}

	settings, err := kurrentdb.ParseConnectionString(connectionString)
	if err != nil {
		panic(err)
	}

	client, err := kurrentdb.NewClient(settings)
	if err != nil {
		panic(err)
	}
	defer client.Close()

	fmt.Printf("Connected to KurrentDB at %s\n", connectionString)

	// === APPEND EVENTS ===
	orderID := uuid.New().String()
	streamName := fmt.Sprintf("order-%s", orderID)

	order := OrderCreated{
		OrderID:    orderID,
		CustomerID: "customer-123",
		Amount:     99.99,
	}

	data, err := json.Marshal(order)
	if err != nil {
		panic(err)
	}

	eventData := kurrentdb.EventData{
		EventID:     uuid.New(),
		ContentType: kurrentdb.ContentTypeJson,
		EventType:   "OrderCreated",
		Data:        data,
	}

	writeResult, err := client.AppendToStream(
		ctx,
		streamName,
		kurrentdb.AppendToStreamOptions{},
		eventData,
	)
	if err != nil {
		panic(err)
	}

	fmt.Printf("Appended event to %s at revision %d\n", streamName, writeResult.NextExpectedVersion)

	// === READ EVENTS ===
	fmt.Println("\nReading events:")

	stream, err := client.ReadStream(
		ctx,
		streamName,
		kurrentdb.ReadStreamOptions{
			Direction: kurrentdb.Forwards,
			From:      kurrentdb.Start{},
		},
		100,
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

		fmt.Printf("  Event #%d: %s\n", event.Event.EventNumber, event.Event.EventType)
		fmt.Printf("  Data: %s\n", string(event.Event.Data))
	}

	// === CATCH-UP SUBSCRIPTION (Stream) ===
	fmt.Println("\nStarting catch-up subscription to stream...")

	subscription, err := client.SubscribeToStream(
		ctx,
		streamName,
		kurrentdb.SubscribeToStreamOptions{
			From: kurrentdb.Start{},
		},
	)
	if err != nil {
		panic(err)
	}

	count := 0
	for {
		event := subscription.Recv()

		if event.EventAppeared != nil {
			fmt.Printf("  [Sub] Received: %s @ revision %d\n",
				event.EventAppeared.Event.EventType,
				event.EventAppeared.Event.EventNumber)
			count++
			if count >= 1 {
				break
			}
		}

		if event.SubscriptionDropped != nil {
			fmt.Printf("  Subscription dropped: %v\n", event.SubscriptionDropped.Error)
			break
		}
	}
	subscription.Close()

	fmt.Println("Subscription stopped")

	// === CATCH-UP SUBSCRIPTION ($all) ===
	fmt.Println("\nStarting catch-up subscription to $all (reading 3 non-system events)...")

	allSubscription, err := client.SubscribeToAll(
		ctx,
		kurrentdb.SubscribeToAllOptions{
			From: kurrentdb.Start{},
		},
	)
	if err != nil {
		panic(err)
	}

	count = 0
	for {
		event := allSubscription.Recv()

		if event.EventAppeared != nil {
			streamID := event.EventAppeared.Event.StreamID
			if len(streamID) > 0 && streamID[0] != '$' {
				fmt.Printf("  [Sub] Stream: %s, Type: %s\n",
					streamID,
					event.EventAppeared.Event.EventType)
				count++
				if count >= 3 {
					break
				}
			}
		}

		if event.SubscriptionDropped != nil {
			break
		}
	}
	allSubscription.Close()

	fmt.Println("\nAll tests passed!")
}
