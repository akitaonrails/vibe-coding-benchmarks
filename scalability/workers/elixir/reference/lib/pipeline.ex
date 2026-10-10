defmodule QueueWorker.Pipeline do
  use Broadway
  alias QueueWorker.Config

  def start_link(_) do
    Broadway.start_link(__MODULE__, name: __MODULE__,
      shutdown: max(100, Config.integer("SHUTDOWN_MS", 5000) - 500),
      producer: [module: {BroadwayRabbitMQ.Producer,
        queue: System.get_env("INPUT_QUEUE", "work"), connection: System.fetch_env!("AMQP_URL"),
        qos: [prefetch_count: Config.integer("PREFETCH", 32)],
        buffer_size: Config.integer("PREFETCH", 32),
        on_success: :ack, on_failure: :reject_and_requeue,
        backoff_min: 1000, backoff_max: 3000}, concurrency: 1],
      processors: [default: [concurrency: Config.integer("MAX_INFLIGHT", 8), max_demand: 1]])
  end

  @impl true
  def handle_message(_, message, _) do
    event = Jason.decode!(message.data)
    effect = %{tenant: event["tenant"], id: event["id"], result: 3 * event["value"] + 7,
               digest: :crypto.hash(:sha256, event["payload"]) |> Base.encode16(case: :lower)}
    case deliver(Jason.encode!(effect), message.data, Config.integer("MAX_ATTEMPTS", 3)) do
      :ok -> message
      :retry -> Broadway.Message.failed(message, :transient_failure)
    end
  end

  defp deliver(body, original, remaining) do
    timeout = Config.integer("REQUEST_TIMEOUT_MS", 1000)
    request = {System.fetch_env!("SINK_URL") |> String.to_charlist(), [], ~c"application/json", body}
    response = :httpc.request(:post, request, [timeout: timeout, connect_timeout: timeout, autoredirect: false], [])
    case response do
      {:ok, {_, headers, _}} -> QueueWorker.Fault.check(headers)
      _ -> :ok
    end
    case response do
      {:ok, {{_, status, _}, _, _}} when status in [200, 201] -> :ok
      {:ok, {{_, 422, _}, _, _}} ->
        try do
          case QueueWorker.Publisher.publish(original) do
            :ok -> :ok
            _ -> pause(); :retry
          end
        catch
          :exit, _ -> pause(); :retry
        end
      _ ->
        pause()
        if remaining > 1, do: deliver(body, original, remaining - 1), else: :retry
    end
  end
  defp pause, do: Process.sleep(Config.integer("RETRY_DELAY_MS", 100))
end
