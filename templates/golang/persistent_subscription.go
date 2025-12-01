// KurrentDB Go Client Example - Persistent Subscriptions
package main

import (
	"context"
	"encoding/json"
	"fmt"

	"github.com/google/uuid"
	"github.com/kurrent-io/KurrentDB-Client-Go/kurrentdb"
)

// OrderCreated represents an order creation event
type OrderCreated struct {
	OrderID string  `json:"orderId"`
	Amount  float64 `json:"amount"`
}

func main() {
	ctx := context.Background()

	// === CONNECTION ===
	settings, err := kurrentdb.ParseConnectionString("kurrentdb://admin:changeit@localhost:2113?tls=false")
	if err != nil {
		panic(err)
	}

	client, err := kurrentdb.NewClient(settings)
	if err != nil {
		panic(err)
	}
	defer client.Close()

	fmt.Println("Connected to KurrentDB")

	streamName := "orders"
	groupName := "order-processor"

	// === CREATE PERSISTENT SUBSCRIPTION ===
	err = client.CreatePersistentSubscription(
		ctx,
		streamName,
		groupName,
		kurrentdb.PersistentStreamSubscriptionOptions{},
	)
	if err != nil {
		// Check if already exists
		fmt.Printf("Persistent subscription '%s' may already exist: %v\n", groupName, err)
	} else {
		fmt.Printf("Created persistent subscription '%s' on stream '%s'\n", groupName, streamName)
	}

	// === APPEND SOME TEST EVENTS ===
	for i := 0; i < 3; i++ {
		order := OrderCreated{
			OrderID: uuid.New().String(),
			Amount:  10.00 * float64(i+1),
		}

		data, _ := json.Marshal(order)

		eventData := kurrentdb.EventData{
			EventID:     uuid.New(),
			ContentType: kurrentdb.ContentTypeJson,
			EventType:   "OrderCreated",
			Data:        data,
		}

		_, err := client.AppendToStream(
			ctx,
			streamName,
			kurrentdb.AppendToStreamOptions{},
			eventData,
		)
		if err != nil {
			panic(err)
		}
		fmt.Printf("Appended OrderCreated event #%d\n", i+1)
	}

	// === SUBSCRIBE TO PERSISTENT SUBSCRIPTION ===
	fmt.Println("\nSubscribing to persistent subscription...")

	subscription, err := client.SubscribeToPersistentSubscription(
		ctx,
		streamName,
		groupName,
		kurrentdb.SubscribeToPersistentSubscriptionOptions{},
	)
	if err != nil {
		panic(err)
	}
	defer subscription.Close()

	count := 0
	for {
		event := subscription.Recv()

		if event.EventAppeared != nil {
			fmt.Printf("  Processing: %s\n", event.EventAppeared.Event.EventType)
			fmt.Printf("  Data: %s\n", string(event.EventAppeared.Event.Data))

			// Simulate processing
			// ... your business logic here ...

			// Acknowledge success
			err := subscription.Ack(event.EventAppeared.Event)
			if err != nil {
				// Park failed event for later inspection
				subscription.Nack("Processing failed", kurrentdb.NackActionPark, event.EventAppeared.Event)
				fmt.Printf("  Parked event: %v\n", err)
			} else {
				fmt.Println("  Acknowledged event")
			}

			count++
			if count >= 3 {
				break
			}
		}

		if event.SubscriptionDropped != nil {
			fmt.Printf("Subscription dropped: %v\n", event.SubscriptionDropped.Error)
			break
		}
	}

	fmt.Println("\nDone!")
}
