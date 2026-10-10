defmodule QueueWorker.Pipeline do
  use Broadway
  def start_link(_) do
    Broadway.start_link(__MODULE__, name: __MODULE__,
      producer: [module: {BroadwayRabbitMQ.Producer,
        queue: System.get_env("INPUT_QUEUE", "work"), connection: System.fetch_env!("AMQP_URL"),
        qos: [prefetch_count: integer("PREFETCH", 32)], on_failure: :reject_and_requeue}, concurrency: 1],
      processors: [default: [concurrency: 1, max_demand: 1]])
  end
  @impl true
  def handle_message(_, message, _) do
    event = Jason.decode!(message.data)
    effect = %{tenant: event["tenant"], id: event["id"], result: 3 * event["value"] + 7,
      digest: :crypto.hash(:sha256, event["payload"]) |> Base.encode16(case: :lower)}
    request = {System.fetch_env!("SINK_URL") |> String.to_charlist(), [], ~c"application/json", Jason.encode!(effect)}
    timeout = integer("REQUEST_TIMEOUT_MS", 1000)
    response = :httpc.request(:post, request, [timeout: timeout, connect_timeout: timeout], [])
    case response do
      {:ok, {_, headers, _}} -> QueueWorker.Fault.check(headers)
      _ -> :ok
    end
    case response do
      {:ok, {{_, status, _}, _, _}} when status in [200, 201] -> message
      _ -> Broadway.Message.failed(message, :failed_request)
    end
  end
  defp integer(name, default), do: System.get_env(name, to_string(default)) |> String.to_integer()
end
