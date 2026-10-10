//! Functioning happy-path consumer. Reliability requirements are the coding task.
mod fault;
use futures_util::StreamExt;
use lapin::{options::*, types::FieldTable, Connection, ConnectionProperties};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{env, time::Duration};

#[derive(Deserialize)]
struct Event {
    tenant: String,
    id: String,
    value: i64,
    payload: String,
}
#[derive(Serialize)]
struct Effect {
    tenant: String,
    id: String,
    result: i64,
    digest: String,
}

#[tokio::main(worker_threads = 2)]
async fn main() -> Result<(), Box<dyn std::error::Error>> {
    let connection =
        Connection::connect(&env::var("AMQP_URL")?, ConnectionProperties::default()).await?;
    let channel = connection.create_channel().await?;
    let prefetch = env::var("PREFETCH")
        .unwrap_or_else(|_| "32".into())
        .parse()?;
    channel
        .basic_qos(prefetch, BasicQosOptions::default())
        .await?;
    let queue = env::var("INPUT_QUEUE").unwrap_or_else(|_| "work".into());
    let mut consumer = channel
        .basic_consume(
            queue.into(),
            "starter".into(),
            BasicConsumeOptions::default(),
            FieldTable::default(),
        )
        .await?;
    let deadline = env::var("REQUEST_TIMEOUT_MS")
        .unwrap_or_else(|_| "1000".into())
        .parse()?;
    let http = reqwest::Client::builder()
        .timeout(Duration::from_millis(deadline))
        .build()?;
    let sink = env::var("SINK_URL")?;
    while let Some(delivery) = consumer.next().await {
        let delivery = delivery?;
        let event: Event = serde_json::from_slice(&delivery.data)?;
        let effect = Effect {
            tenant: event.tenant,
            id: event.id,
            result: 3 * event.value + 7,
            digest: Sha256::digest(event.payload.as_bytes())
                .iter()
                .map(|byte| format!("{byte:02x}"))
                .collect(),
        };
        let success = http
            .post(&sink)
            .json(&effect)
            .send()
            .await
            .is_ok_and(|response| {
                fault::check(response.headers());
                matches!(response.status().as_u16(), 200 | 201)
            });
        if success {
            delivery.ack(BasicAckOptions::default()).await?;
        } else {
            delivery
                .nack(BasicNackOptions {
                    multiple: false,
                    requeue: true,
                })
                .await?;
        }
    }
    Ok(())
}
