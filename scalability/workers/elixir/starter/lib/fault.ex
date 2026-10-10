defmodule QueueWorker.Fault do
  @moduledoc "Evaluator-required handler failure hook; keep this source unchanged."
  def check(headers) do
    if Enum.any?(headers, fn {name, value} ->
      String.downcase(to_string(name)) == "x-langbench-fault" and to_string(value) == "handler-crash"
    end) do
      raise "LANGBENCH_HANDLER_CRASH"
    end
    :ok
  end
end
