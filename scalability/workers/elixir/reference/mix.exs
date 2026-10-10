defmodule QueueWorker.MixProject do
  use Mix.Project
  def project do
    [app: :queue_worker, version: "0.1.0", elixir: "~> 1.18", start_permanent: Mix.env() == :prod,
     deps: [{:broadway, "== 1.3.0"}, {:broadway_rabbitmq, "== 0.8.2"},
            {:amqp, "== 4.3.0"}, {:jason, "== 1.4.5"}]]
  end
  def application do
    [extra_applications: [:logger, :crypto, :inets], mod: {QueueWorker.Application, []}]
  end
end
