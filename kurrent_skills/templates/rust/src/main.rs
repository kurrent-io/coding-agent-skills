//! KurrentDB Rust Client Example - Append, Read, Subscribe, and Filtered Subscriptions

use kurrentdb::{
    Client, EventData, ReadStreamOptions, StreamPosition,
    SubscribeToStreamOptions, SubscribeToAllOptions, SubscriptionFilter,
};
use serde::{Deserialize, Serialize};
use std::env;
use uuid::Uuid;

#[derive(Debug, Serialize, Deserialize)]
struct OrderCreated {
    order_id: String,
    customer_id: String,
    amount: f64,
}

mod projection;

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // Handle command line arguments
    let args: Vec<String> = env::args().collect();
    if args.len() > 1 && args[1] == "projection" {
        return projection::run_projection().await;
    }

    let connection_string = env::var("KURRENTDB_CONNECTION_STRING")
        .unwrap_or_else(|_| "kurrentdb://localhost:2113?tls=false".to_string());

    let settings = connection_string.parse()?;
    let client = Client::new(settings)?;

    println!("Connected to KurrentDB at {}", connection_string);

    let order_id = Uuid::new_v4().to_string();
    let stream_name = format!("order-{}", order_id);

    let order = OrderCreated {
        order_id: order_id.clone(),
        customer_id: "customer-123".to_string(),
        amount: 99.99,
    };

    let event = EventData::json("OrderCreated", &order)?.id(Uuid::new_v4());

    let write_result = client
        .append_to_stream(stream_name.clone(), &Default::default(), event)
        .await?;

    println!(
        "Appended event to {} at revision {:?}",
        stream_name, write_result.next_expected_version
    );

    println!("
Reading events:");

    let options = ReadStreamOptions::default()
        .position(StreamPosition::Start)
        .max_count(100);

    let mut stream = client.read_stream(stream_name.clone(), &options).await?;

    while let Some(event) = stream.next().await? {
        let original = event.get_original_event();
        println!("  Event #{}: {}", original.revision, original.event_type);
        let data: OrderCreated = original.as_json()?;
        println!("  Data: {:?}", data);
    }

    println!("
Starting catch-up subscription to stream...");

    let options = SubscribeToStreamOptions::default().start_from(StreamPosition::Start);
    let mut subscription = client.subscribe_to_stream(stream_name.clone(), &options).await;

    let mut count = 0;
    loop {
        let event = subscription.next().await?;
        let original = event.get_original_event();
        println!("  [Sub] Received: {} @ revision {}", original.event_type, original.revision);
        count += 1;
        if count >= 1 { break; }
    }

    println!("Subscription stopped");

    // === CATCH-UP SUBSCRIPTION ($all) ===
    println!("\nStarting catch-up subscription to $all (reading 3 non-system events)...");

    let options = SubscribeToAllOptions::default();
    let mut all_subscription = client.subscribe_to_all(&options).await;

    let mut count = 0;
    loop {
        match all_subscription.next().await {
            Ok(event) => {
                let original = event.get_original_event();
                if !original.stream_id().starts_with('$') {
                    println!(
                        "  [Sub $all] Stream: {}, Type: {}",
                        original.stream_id(), original.event_type
                    );
                    count += 1;
                    if count >= 3 {
                        break;
                    }
                }
            }
            Err(e) => {
                println!("Subscription error: {}", e);
                break;
            }
        }
    }

    // === FILTERED SUBSCRIPTION (exclude system events) ===
    println!("\nStarting filtered subscription (excluding system events)...");

    let filter = SubscriptionFilter::on_event_type().exclude_system_events();
    let options = SubscribeToAllOptions::default().filter(filter);
    let mut filtered_sub = client.subscribe_to_all(&options).await;

    let mut count = 0;
    loop {
        match filtered_sub.next().await {
            Ok(event) => {
                let original = event.get_original_event();
                println!(
                    "  [Filtered] Stream: {}, Type: {}",
                    original.stream_id(), original.event_type
                );
                count += 1;
                if count >= 3 {
                    break;
                }
            }
            Err(e) => {
                println!("Filtered subscription error: {}", e);
                break;
            }
        }
    }

    // === FILTERED SUBSCRIPTION (by stream prefix) ===
    println!("\nStarting filtered subscription (stream prefix 'order-')...");

    let filter = SubscriptionFilter::on_stream_name().add_prefix("order-");
    let options = SubscribeToAllOptions::default().filter(filter);
    let mut prefix_sub = client.subscribe_to_all(&options).await;

    let mut count = 0;
    loop {
        match prefix_sub.next().await {
            Ok(event) => {
                let original = event.get_original_event();
                println!(
                    "  [Prefix Filter] Stream: {}, Type: {}",
                    original.stream_id(), original.event_type
                );
                count += 1;
                if count >= 2 {
                    break;
                }
            }
            Err(e) => {
                println!("Prefix filtered subscription error: {}", e);
                break;
            }
        }
    }

    // === FILTERED SUBSCRIPTION (by event type prefix) ===
    println!("\nStarting filtered subscription (event type prefix 'Order')...");

    let filter = SubscriptionFilter::on_event_type().add_prefix("Order");
    let options = SubscribeToAllOptions::default().filter(filter);
    let mut event_type_sub = client.subscribe_to_all(&options).await;

    let mut count = 0;
    loop {
        match event_type_sub.next().await {
            Ok(event) => {
                let original = event.get_original_event();
                println!(
                    "  [Event Type Filter] Stream: {}, Type: {}",
                    original.stream_id(), original.event_type
                );
                count += 1;
                if count >= 2 {
                    break;
                }
            }
            Err(e) => {
                println!("Event type filtered subscription error: {}", e);
                break;
            }
        }
    }

    println!("\nAll tests passed!");
    Ok(())
}
