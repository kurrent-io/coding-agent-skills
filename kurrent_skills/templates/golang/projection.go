// KurrentDB Go In-Memory Projection Example
// Demonstrates: Subscribe to events, build state, track checkpoint
package main

import (
	"context"
	"encoding/json"
	"fmt"
	"os"

	"github.com/google/uuid"
	"github.com/kurrent-io/KurrentDB-Client-Go/kurrentdb"
)

// === MINIMAL PROJECTION FRAMEWORK ===

type EventHandler func(state map[string]interface{}, data map[string]interface{}) map[string]interface{}

type Projection struct {
	Name       string
	State      map[string]map[string]interface{}
	Checkpoint *kurrentdb.Position
	handlers   map[string]EventHandler
}

func NewProjection(name string) *Projection {
	return &Projection{
		Name:     name,
		State:    make(map[string]map[string]interface{}),
		handlers: make(map[string]EventHandler),
	}
}

func (p *Projection) On(eventType string, handler EventHandler) *Projection {
	p.handlers[eventType] = handler
	return p
}

func (p *Projection) Get(streamID string) map[string]interface{} {
	return p.State[streamID]
}

func (p *Projection) Apply(event *kurrentdb.RecordedEvent, position kurrentdb.Position) bool {
	handler, ok := p.handlers[event.EventType]
	if !ok {
		return false
	}

	streamID := event.StreamID
	current := p.State[streamID]
	if current == nil {
		current = make(map[string]interface{})
	}

	var data map[string]interface{}
	json.Unmarshal(event.Data, &data)

	p.State[streamID] = handler(current, data)
	p.Checkpoint = &position
	return true
}

// === ORDER EVENTS (for projection) ===

type ProjectionOrderCreated struct {
	OrderID    string  `json:"orderId"`
	CustomerID string  `json:"customerId"`
	Amount     float64 `json:"amount"`
}

type ProjectionItemAdded struct {
	Item  string  `json:"item"`
	Price float64 `json:"price"`
}

type ProjectionOrderShipped struct {
	ShippedAt string `json:"shippedAt"`
}

// RunProjection runs the in-memory projection example
func RunProjection() {
	ctx := context.Background()

	// === SETUP ===
	connectionString := os.Getenv("KURRENTDB_CONNECTION_STRING")
	if connectionString == "" {
		connectionString = "esdb://localhost:2113?tls=false"
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

	// === DEFINE PROJECTION ===
	orderProjection := NewProjection("OrderSummary").
		On("OrderCreated", func(state map[string]interface{}, data map[string]interface{}) map[string]interface{} {
			return map[string]interface{}{
				"orderId":    data["orderId"],
				"customerId": data["customerId"],
				"amount":     data["amount"],
				"status":     "created",
				"items":      []string{},
			}
		}).
		On("ItemAdded", func(state map[string]interface{}, data map[string]interface{}) map[string]interface{} {
			items := state["items"].([]string)
			amount := state["amount"].(float64)
			state["items"] = append(items, data["item"].(string))
			state["amount"] = amount + data["price"].(float64)
			return state
		}).
		On("OrderShipped", func(state map[string]interface{}, data map[string]interface{}) map[string]interface{} {
			state["status"] = "shipped"
			state["shippedAt"] = data["shippedAt"]
			return state
		}).
		On("OrderCompleted", func(state map[string]interface{}, data map[string]interface{}) map[string]interface{} {
			state["status"] = "completed"
			return state
		})

	// === TEST: Append test events ===
	fmt.Println("\n=== Appending test events ===")

	orderId1 := uuid.New().String()
	orderId2 := uuid.New().String()
	stream1 := fmt.Sprintf("order-%s", orderId1)
	stream2 := fmt.Sprintf("order-%s", orderId2)

	makeEvent := func(eventType string, data interface{}) kurrentdb.EventData {
		jsonData, _ := json.Marshal(data)
		return kurrentdb.EventData{
			EventID:     uuid.New(),
			ContentType: kurrentdb.ContentTypeJson,
			EventType:   eventType,
			Data:        jsonData,
		}
	}

	// Order 1: Created -> ItemAdded -> Shipped -> Completed
	client.AppendToStream(ctx, stream1, kurrentdb.AppendToStreamOptions{},
		makeEvent("OrderCreated", ProjectionOrderCreated{OrderID: orderId1, CustomerID: "cust-1", Amount: 100}))
	client.AppendToStream(ctx, stream1, kurrentdb.AppendToStreamOptions{},
		makeEvent("ItemAdded", ProjectionItemAdded{Item: "Widget", Price: 25}))
	client.AppendToStream(ctx, stream1, kurrentdb.AppendToStreamOptions{},
		makeEvent("OrderShipped", ProjectionOrderShipped{ShippedAt: "2024-01-15T10:00:00Z"}))
	client.AppendToStream(ctx, stream1, kurrentdb.AppendToStreamOptions{},
		makeEvent("OrderCompleted", struct{}{}))

	// Order 2: Created -> ItemAdded (still pending)
	client.AppendToStream(ctx, stream2, kurrentdb.AppendToStreamOptions{},
		makeEvent("OrderCreated", ProjectionOrderCreated{OrderID: orderId2, CustomerID: "cust-2", Amount: 50}))
	client.AppendToStream(ctx, stream2, kurrentdb.AppendToStreamOptions{},
		makeEvent("ItemAdded", ProjectionItemAdded{Item: "Gadget", Price: 30}))

	fmt.Printf("Created order streams: %s, %s\n", stream1, stream2)

	// === RUN PROJECTION ===
	fmt.Println("\n=== Running projection ===")

	subscription, err := client.SubscribeToAll(ctx, kurrentdb.SubscribeToAllOptions{
		From:   kurrentdb.Start{},
		Filter: kurrentdb.ExcludeSystemEventsFilter(),
	})
	if err != nil {
		panic(err)
	}

	processedCount := 0
	targetStreams := map[string]bool{stream1: true, stream2: true}
	targetEventsCount := map[string]int{stream1: 0, stream2: 0}
	expectedCounts := map[string]int{stream1: 4, stream2: 2} // Order 1: 4 events, Order 2: 2 events

	for {
		event := subscription.Recv()

		if event.SubscriptionDropped != nil {
			break
		}

		if event.EventAppeared != nil {
			evt := event.EventAppeared.OriginalEvent()
			position := event.EventAppeared.OriginalEvent().Position

			if orderProjection.Apply(evt, position) {
				processedCount++
				fmt.Printf("  Processed: %s on %s\n", evt.EventType, evt.StreamID)

				if targetStreams[evt.StreamID] {
					targetEventsCount[evt.StreamID]++
				}
			}

			// Stop when we've processed all our test events for both streams
			if targetEventsCount[stream1] >= expectedCounts[stream1] &&
				targetEventsCount[stream2] >= expectedCounts[stream2] {
				break
			}

			// Safety limit
			if processedCount > 200 {
				break
			}
		}
	}
	subscription.Close()

	// === VERIFY RESULTS ===
	fmt.Println("\n=== Projection Results ===")

	order1State := orderProjection.Get(stream1)
	order2State := orderProjection.Get(stream2)

	order1JSON, _ := json.MarshalIndent(order1State, "", "  ")
	order2JSON, _ := json.MarshalIndent(order2State, "", "  ")

	fmt.Printf("\nOrder 1 (%s):\n%s\n", stream1, string(order1JSON))
	fmt.Printf("\nOrder 2 (%s):\n%s\n", stream2, string(order2JSON))

	// === ASSERTIONS ===
	fmt.Println("\n=== Running assertions ===")

	passed := true

	// Order 1 assertions
	if order1State["status"] != "completed" {
		fmt.Printf("FAIL: Order 1 status should be 'completed', got '%v'\n", order1State["status"])
		passed = false
	}
	if order1State["amount"].(float64) != 125 {
		fmt.Printf("FAIL: Order 1 amount should be 125, got %v\n", order1State["amount"])
		passed = false
	}
	if len(order1State["items"].([]string)) != 1 {
		fmt.Printf("FAIL: Order 1 should have 1 item, got %d\n", len(order1State["items"].([]string)))
		passed = false
	}

	// Order 2 assertions
	if order2State["status"] != "created" {
		fmt.Printf("FAIL: Order 2 status should be 'created', got '%v'\n", order2State["status"])
		passed = false
	}
	if order2State["amount"].(float64) != 80 {
		fmt.Printf("FAIL: Order 2 amount should be 80, got %v\n", order2State["amount"])
		passed = false
	}

	// Checkpoint assertion
	if orderProjection.Checkpoint == nil {
		fmt.Println("FAIL: Checkpoint should be set")
		passed = false
	}

	if passed {
		fmt.Println("\nAll projection tests passed!")
	} else {
		fmt.Println("\nSome tests failed!")
		os.Exit(1)
	}
}

// Uncomment to run as standalone:
// func main() {
// 	runProjection()
// }
