mod fault;
use futures_util::TryStreamExt;
use lapin::{
    message::Delivery, options::*, types::FieldTable, BasicProperties, Channel, Connection,
    ConnectionProperties,
};
use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::{env, sync::Arc, time::Duration};
use tokio::{
    signal::unix::{signal, SignalKind},
    time::{sleep, timeout},
};

#[derive(Clone)]
struct Config {
    amqp: String,
    input: String,
    dead: String,
    sink: String,
    prefetch: u16,
    inflight: usize,
    attempts: usize,
    request_timeout: Duration,
    retry_delay: Duration,
}
impl Config {
    fn load() -> Self {
        fn value(name: &str, default: &str) -> String {
            env::var(name).unwrap_or_else(|_| default.into())
        }
        fn number(name: &str, default: &str) -> u64 {
            value(name, default)
                .parse()
                .expect("numeric environment limit")
        }
        Self {
            amqp: env::var("AMQP_URL").expect("AMQP_URL"),
            input: value("INPUT_QUEUE", "work"),
            dead: value("DLQ_QUEUE", "dead"),
            sink: env::var("SINK_URL").expect("SINK_URL"),
            prefetch: number("PREFETCH", "32").try_into().unwrap(),
            inflight: number("MAX_INFLIGHT", "8") as usize,
            attempts: number("MAX_ATTEMPTS", "3") as usize,
            request_timeout: Duration::from_millis(number("REQUEST_TIMEOUT_MS", "1000")),
            retry_delay: Duration::from_millis(number("RETRY_DELAY_MS", "100")),
        }
    }
}
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
fn effect(bytes: &[u8]) -> Effect {
    let event: Event = serde_json::from_slice(bytes).expect("well-formed contract event");
    Effect {
        tenant: event.tenant,
        id: event.id,
        result: 3 * event.value + 7,
        digest: Sha256::digest(event.payload.as_bytes())
            .iter()
            .map(|b| format!("{b:02x}"))
            .collect(),
    }
}
async fn process(
    delivery: Delivery,
    publisher: Channel,
    http: reqwest::Client,
    config: Arc<Config>,
) -> lapin::Result<()> {
    let effect = effect(&delivery.data);
    for _ in 0..config.attempts {
        let response = http.post(&config.sink).json(&effect).send().await;
        if let Ok(response) = &response {
            fault::check(response.headers());
        }
        match response.map(|response| response.status().as_u16()) {
            Ok(200 | 201) => return delivery.ack(BasicAckOptions::default()).await.map(|_| ()),
            Ok(422) => {
                // Persist a confirmed original event before relinquishing its input delivery.
                let confirmed = timeout(config.request_timeout, async {
                    publisher
                        .basic_publish(
                            "".into(),
                            config.dead.clone().into(),
                            BasicPublishOptions::default(),
                            &delivery.data,
                            BasicProperties::default()
                                .with_delivery_mode(2)
                                .with_content_type("application/json".into()),
                        )
                        .await?
                        .await
                })
                .await;
                if matches!(confirmed, Ok(Ok(lapin::Confirmation::Ack(_)))) {
                    return delivery.ack(BasicAckOptions::default()).await.map(|_| ());
                }
                break;
            }
            _ => sleep(config.retry_delay).await,
        }
    }
    // The poison publish-failure path also waits before requeueing.
    sleep(config.retry_delay).await;
    delivery
        .nack(BasicNackOptions {
            requeue: true,
            multiple: false,
        })
        .await
        .map(|_| ())
}
// Aborting siblings on session failure prevents detached handlers crossing the concurrency bound.
struct HandlerTask(tokio::task::JoinHandle<lapin::Result<()>>);
impl Drop for HandlerTask {
    fn drop(&mut self) {
        self.0.abort();
    }
}
async fn session(config: Arc<Config>, http: reqwest::Client) -> lapin::Result<()> {
    let connection = Connection::connect(&config.amqp, ConnectionProperties::default()).await?;
    let input = connection.create_channel().await?;
    let publisher = connection.create_channel().await?;
    input
        .basic_qos(config.prefetch, BasicQosOptions::default())
        .await?;
    publisher
        .confirm_select(ConfirmSelectOptions::default())
        .await?;
    let deliveries = input
        .basic_consume(
            config.input.clone().into(),
            "queue-worker".into(),
            BasicConsumeOptions::default(),
            FieldTable::default(),
        )
        .await?;
    println!("{{\"ready\":true}}");
    let result = deliveries
        .try_for_each_concurrent(config.inflight, |delivery| {
            let mut task = HandlerTask(tokio::spawn(process(
                delivery,
                publisher.clone(),
                http.clone(),
                config.clone(),
            )));
            async move {
                match (&mut task.0).await {
                    Ok(result) => result,
                    Err(error) => Err(std::io::Error::other(error).into()),
                }
            }
        })
        .await;
    let _ = timeout(
        Duration::from_millis(500),
        connection.close(200, "session ended".into()),
    )
    .await;
    result
}
#[tokio::main(worker_threads = 2)]
async fn main() {
    let config = Arc::new(Config::load());
    assert!(config.prefetch > 0 && config.inflight > 0 && config.attempts > 0);
    let http = reqwest::Client::builder()
        .timeout(config.request_timeout)
        .redirect(reqwest::redirect::Policy::none())
        .build()
        .unwrap();
    let mut term = signal(SignalKind::terminate()).unwrap();
    let run = async {
        loop {
            if let Err(error) = session(config.clone(), http.clone()).await {
                eprintln!("broker session ended: {error}");
            }
            sleep(Duration::from_secs(1)).await;
        }
    };
    tokio::select! { _ = run => {}, _ = term.recv() => {} }
    // Dropping the connection/process requeues unacknowledged deliveries; no local acknowledged backlog exists.
}
