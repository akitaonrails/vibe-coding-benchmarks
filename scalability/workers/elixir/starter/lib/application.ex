defmodule QueueWorker.Application do
  use Application
  def start(_type, _args) do
    Supervisor.start_link([QueueWorker.Pipeline], strategy: :one_for_one, name: QueueWorker.Supervisor)
  end
end
