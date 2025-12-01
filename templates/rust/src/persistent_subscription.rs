//! KurrentDB Rust Client Example - Persistent Subscriptions

use kurrentdb::{Client, EventData, NakAction, PersistentSubscriptionOptions};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Serialize, Deserialize)]
struct OrderCreated {
    order_id: String,
    amount: f64,
}

#[tokio::main]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    // === CONNECTION ===
    let settings = "kurrentdb://admin:changeit@localhost:2113?tls=false".parse()?;
    let client = Client::new(settings)?;

    println!("Connected to KurrentDB");

    let stream_name = "orders";
    let group_name = "order-processor";

    // === CREATE PERSISTENT SUBSCRIPTION ===
    match client
        .create_persistent_subscription(stream_name, group_name, &Default::default())
        .await
    {
        Ok(_) => {
            println!(
                "Created persistent subscription '{}' on stream '{}'",
                group_name, stream_name
            );
        }
        Err(e) => {
            println!(
                "Persistent subscription '{}' may already exist: {}",
                group_name, e
            );
        }
    }

    // === APPEND SOME TEST EVENTS ===
    for i in 0..3 {
        let order = OrderCreated {
            order_id: Uuid::new_v4().to_string(),
            amount: 10.0 * (i + 1) as f64,
        };

        let event = EventData::json("OrderCreated", &order)?.id(Uuid::new_v4());

        client
            .append_to_stream(stream_name, &Default::default(), event)
            .await?;

        println!("Appended OrderCreated event #{}", i + 1);
    }

    // === SUBSCRIBE TO PERSISTENT SUBSCRIPTION ===
    println!("\nSubscribing to persistent subscription...");

    let mut subscription = client
        .subscribe_to_persistent_subscription(stream_name, group_name, &Default::default())
        .await?;

    let mut count = 0;
    loop {
        match subscription.next().await {
            Ok(event) => {
                let original = event.get_original_event();
                println!("  Processing: {}", original.event_type);

                let data: OrderCreated = original.as_json()?;
                println!("  Data: {:?}", data);

                // Simulate processing
                // ... your business logic here ...

                // Acknowledge success
                match subscription.ack(&event).await {
                    Ok(_) => {
                        println!("  Acknowledged event");
                    }
                    Err(e) => {
                        // Park failed event for later inspection
                        subscription.nack(&event, NakAction::Park).await?;
                        println!("  Parked event: {}", e);
                    }
                }

                count += 1;
                if count >= 3 {
                    break;
                }
            }
            Err(e) => {
                println!("Subscription error: {}", e);
                break;
            }
        }
    }

    println!("\nDone!");
    Ok(())
}
