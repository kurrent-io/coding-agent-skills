//! KurrentDB Rust In-Memory Projection Example
//! Demonstrates: Subscribe to events, build state, track checkpoint

use kurrentdb::{
    Client, EventData, Position, SubscribeToAllOptions, SubscriptionFilter,
};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use std::collections::HashMap;
use std::env;
use uuid::Uuid;

// === MINIMAL PROJECTION FRAMEWORK ===

type EventHandler = Box<dyn Fn(&Value, &Value) -> Value + Send + Sync>;

pub struct Projection {
    pub name: String,
    pub state: HashMap<String, Value>,
    pub checkpoint: Option<Position>,
    handlers: HashMap<String, EventHandler>,
}

impl Projection {
    pub fn new(name: &str) -> Self {
        Self {
            name: name.to_string(),
            state: HashMap::new(),
            checkpoint: None,
            handlers: HashMap::new(),
        }
    }

    pub fn on<F>(mut self, event_type: &str, handler: F) -> Self
    where
        F: Fn(&Value, &Value) -> Value + Send + Sync + 'static,
    {
        self.handlers.insert(event_type.to_string(), Box::new(handler));
        self
    }

    pub fn get(&self, stream_id: &str) -> Option<&Value> {
        self.state.get(stream_id)
    }

    pub fn apply(&mut self, stream_id: &str, event_type: &str, data: &[u8], position: Position) -> bool {
        if let Some(handler) = self.handlers.get(event_type) {
            let current = self.state.get(stream_id).cloned().unwrap_or(json!({}));
            let event_data: Value = serde_json::from_slice(data).unwrap_or(json!({}));
            let new_state = handler(&current, &event_data);
            self.state.insert(stream_id.to_string(), new_state);
            self.checkpoint = Some(position);
            return true;
        }
        false
    }
}

// === ORDER EVENTS ===

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct OrderCreated {
    order_id: String,
    customer_id: String,
    amount: f64,
}

#[derive(Debug, Serialize, Deserialize)]
struct ItemAdded {
    item: String,
    price: f64,
}

#[derive(Debug, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct OrderShipped {
    shipped_at: String,
}

pub async fn run_projection() -> Result<(), Box<dyn std::error::Error>> {
    // === SETUP ===
    let connection_string = env::var("KURRENTDB_CONNECTION_STRING")
        .unwrap_or_else(|_| "kurrentdb://localhost:2113?tls=false".to_string());

    let settings = connection_string.parse()?;
    let client = Client::new(settings)?;

    println!("Connected to KurrentDB at {}", connection_string);

    // === DEFINE PROJECTION ===
    let mut order_projection = Projection::new("OrderSummary")
        .on("OrderCreated", |_state, data| {
            json!({
                "orderId": data.get("orderId"),
                "customerId": data.get("customerId"),
                "amount": data.get("amount"),
                "status": "created",
                "items": []
            })
        })
        .on("ItemAdded", |state, data| {
            let mut new_state = state.clone();
            if let Some(items) = new_state.get_mut("items") {
                if let Some(arr) = items.as_array_mut() {
                    arr.push(json!(data.get("item")));
                }
            }
            if let (Some(current), Some(price)) = (
                new_state.get("amount").and_then(|v| v.as_f64()),
                data.get("price").and_then(|v| v.as_f64()),
            ) {
                new_state["amount"] = json!(current + price);
            }
            new_state
        })
        .on("OrderShipped", |state, data| {
            let mut new_state = state.clone();
            new_state["status"] = json!("shipped");
            new_state["shippedAt"] = json!(data.get("shippedAt"));
            new_state
        })
        .on("OrderCompleted", |state, _data| {
            let mut new_state = state.clone();
            new_state["status"] = json!("completed");
            new_state
        });

    // === TEST: Append test events ===
    println!("\n=== Appending test events ===");

    let order_id_1 = Uuid::new_v4().to_string();
    let order_id_2 = Uuid::new_v4().to_string();
    let stream_1 = format!("order-{}", order_id_1);
    let stream_2 = format!("order-{}", order_id_2);

    // Order 1: Created -> ItemAdded -> Shipped -> Completed
    let event = EventData::json("OrderCreated", &OrderCreated {
        order_id: order_id_1.clone(),
        customer_id: "cust-1".to_string(),
        amount: 100.0,
    })?.id(Uuid::new_v4());
    client.append_to_stream(stream_1.clone(), &Default::default(), event).await?;

    let event = EventData::json("ItemAdded", &ItemAdded {
        item: "Widget".to_string(),
        price: 25.0,
    })?.id(Uuid::new_v4());
    client.append_to_stream(stream_1.clone(), &Default::default(), event).await?;

    let event = EventData::json("OrderShipped", &OrderShipped {
        shipped_at: "2024-01-15T10:00:00Z".to_string(),
    })?.id(Uuid::new_v4());
    client.append_to_stream(stream_1.clone(), &Default::default(), event).await?;

    let event = EventData::json("OrderCompleted", &json!({}))?.id(Uuid::new_v4());
    client.append_to_stream(stream_1.clone(), &Default::default(), event).await?;

    // Order 2: Created -> ItemAdded (still pending)
    let event = EventData::json("OrderCreated", &OrderCreated {
        order_id: order_id_2.clone(),
        customer_id: "cust-2".to_string(),
        amount: 50.0,
    })?.id(Uuid::new_v4());
    client.append_to_stream(stream_2.clone(), &Default::default(), event).await?;

    let event = EventData::json("ItemAdded", &ItemAdded {
        item: "Gadget".to_string(),
        price: 30.0,
    })?.id(Uuid::new_v4());
    client.append_to_stream(stream_2.clone(), &Default::default(), event).await?;

    println!("Created order streams: {}, {}", stream_1, stream_2);

    // === RUN PROJECTION ===
    println!("\n=== Running projection ===");

    let filter = SubscriptionFilter::on_event_type().exclude_system_events();
    let options = SubscribeToAllOptions::default().filter(filter);
    let mut subscription = client.subscribe_to_all(&options).await;

    let mut processed_count = 0;
    let mut target_events_count: HashMap<String, i32> = HashMap::new();
    target_events_count.insert(stream_1.clone(), 0);
    target_events_count.insert(stream_2.clone(), 0);
    let expected_counts: HashMap<String, i32> =
        [(stream_1.clone(), 4), (stream_2.clone(), 2)].into_iter().collect();

    loop {
        match subscription.next().await {
            Ok(event) => {
                let original = event.get_original_event();
                let stream_id = original.stream_id();
                let event_type = &original.event_type;
                let position = original.position;

                if order_projection.apply(stream_id, event_type, &original.data, position) {
                    processed_count += 1;
                    println!("  Processed: {} on {}", event_type, stream_id);

                    if let Some(count) = target_events_count.get_mut(stream_id) {
                        *count += 1;
                    }
                }

                // Stop when we've processed all test events for both streams
                let stream1_done = target_events_count.get(&stream_1).unwrap_or(&0) >= expected_counts.get(&stream_1).unwrap_or(&4);
                let stream2_done = target_events_count.get(&stream_2).unwrap_or(&0) >= expected_counts.get(&stream_2).unwrap_or(&2);
                if stream1_done && stream2_done {
                    break;
                }

                // Safety limit
                if processed_count > 200 {
                    break;
                }
            }
            Err(e) => {
                println!("Subscription error: {}", e);
                break;
            }
        }
    }

    // === VERIFY RESULTS ===
    println!("\n=== Projection Results ===");

    let order1_state = order_projection.get(&stream_1);
    let order2_state = order_projection.get(&stream_2);

    println!("\nOrder 1 ({}):", stream_1);
    println!("{}", serde_json::to_string_pretty(&order1_state)?);

    println!("\nOrder 2 ({}):", stream_2);
    println!("{}", serde_json::to_string_pretty(&order2_state)?);

    // === ASSERTIONS ===
    println!("\n=== Running assertions ===");

    let mut passed = true;

    // Order 1 assertions
    if let Some(state) = order1_state {
        if state.get("status").and_then(|v| v.as_str()) != Some("completed") {
            println!("FAIL: Order 1 status should be 'completed', got {:?}", state.get("status"));
            passed = false;
        }
        if state.get("amount").and_then(|v| v.as_f64()) != Some(125.0) {
            println!("FAIL: Order 1 amount should be 125, got {:?}", state.get("amount"));
            passed = false;
        }
        if state.get("items").and_then(|v| v.as_array()).map(|a| a.len()) != Some(1) {
            println!("FAIL: Order 1 should have 1 item");
            passed = false;
        }
    } else {
        println!("FAIL: Order 1 state not found");
        passed = false;
    }

    // Order 2 assertions
    if let Some(state) = order2_state {
        if state.get("status").and_then(|v| v.as_str()) != Some("created") {
            println!("FAIL: Order 2 status should be 'created', got {:?}", state.get("status"));
            passed = false;
        }
        if state.get("amount").and_then(|v| v.as_f64()) != Some(80.0) {
            println!("FAIL: Order 2 amount should be 80, got {:?}", state.get("amount"));
            passed = false;
        }
    } else {
        println!("FAIL: Order 2 state not found");
        passed = false;
    }

    // Checkpoint assertion
    if order_projection.checkpoint.is_none() {
        println!("FAIL: Checkpoint should be set");
        passed = false;
    }

    if passed {
        println!("\nAll projection tests passed!");
    } else {
        println!("\nSome tests failed!");
        std::process::exit(1);
    }

    Ok(())
}

// Uncomment to run as standalone:
// #[tokio::main]
// async fn main() -> Result<(), Box<dyn std::error::Error>> {
//     run_projection().await
// }
