//! KurrentDB Rust Client Example - Persistent Subscriptions with all NACK actions

use kurrentdb::{Client, EventData, NakAction, PersistentSubscriptionOptions};
use serde::{Deserialize, Serialize};
use uuid::Uuid;

#[derive(Debug, Serialize, Deserialize)]
struct OrderCreated {
    order_id: String,
    amount: f64,
}

// === NACK ACTIONS ===
// Available NACK actions for persistent subscriptions:
// - NakAction::Park  : Move to parked queue for manual inspection
// - NakAction::Retry : Retry processing immediately
// - NakAction::Skip  : Skip this event and continue
// - NakAction::Stop  : Stop the subscription

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

                // Simulate processing with different outcomes based on amount
                if data.amount > 25.0 {
                    // Simulate transient failure - retry immediately
                    subscription.nack(&event, NakAction::Retry).await?;
                    println!("  Retrying event (transient failure)");
                } else if data.amount > 20.0 {
                    // Simulate permanent failure - park for inspection
                    subscription.nack(&event, NakAction::Park).await?;
                    println!("  Parked event (permanent failure)");
                } else if data.amount > 15.0 {
                    // Skip malformed/invalid event
                    subscription.nack(&event, NakAction::Skip).await?;
                    println!("  Skipped event (invalid data)");
                } else {
                    // Success - acknowledge
                    match subscription.ack(&event).await {
                        Ok(_) => {
                            println!("  Acknowledged event");
                        }
                        Err(e) => {
                            subscription.nack(&event, NakAction::Park).await?;
                            println!("  Parked event due to error: {}", e);
                        }
                    }
                }
                // Note: NakAction::Stop would stop the subscription

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
