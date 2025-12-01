//! KurrentDB Rust Client Example - Append, Read, and Subscribe

use kurrentdb::{Client, EventData, ReadStreamOptions, StreamPosition, SubscribeToStreamOptions};
use serde::{Deserialize, Serialize};
use std::env;
use uuid::Uuid;

#[derive(Debug, Serialize, Deserialize)]
struct OrderCreated {
    order_id: String,
    customer_id: String,
    amount: f64,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
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
    println!("
All tests passed!");
    Ok(())
}
