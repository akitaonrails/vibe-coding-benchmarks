defmodule QueueWorker.Config do
  def integer(name, default), do: System.get_env(name, to_string(default)) |> String.to_integer()
end

defmodule QueueWorker.Application do
  use Application
  def start(_type, _args) do
    :httpc.set_options(max_sessions: QueueWorker.Config.integer("MAX_INFLIGHT", 8))
    children = [QueueWorker.Publisher, {QueueWorker.Pipeline, []}]
    Supervisor.start_link(children, strategy: :one_for_one, name: QueueWorker.Supervisor)
  end
end
