defmodule QueueWorker.Publisher do
  use GenServer
  def start_link(_), do: GenServer.start_link(__MODULE__, nil, name: __MODULE__)
  def publish(body), do: GenServer.call(__MODULE__, {:publish, body}, :infinity)
  def init(nil) do
    Process.flag(:trap_exit, true)
    {:ok, nil}
  end
  def handle_call({:publish, body}, _from, previous) do
    state = connect(previous)
    outcome =
      try do
        case state do
          nil -> :error
          {_connection, channel} ->
            with :ok <- AMQP.Basic.publish(channel, "", System.get_env("DLQ_QUEUE", "dead"), body,
                                           persistent: true, content_type: "application/json"),
                 true <- AMQP.Confirm.wait_for_confirms(channel, {1000, :millisecond}) do
              :ok
            else
              _ -> :error
            end
        end
      catch
        :exit, _ -> :error
      end
    if outcome == :ok do
      {:reply, :ok, state}
    else
      disconnect(state)
      {:reply, :error, nil}
    end
  end
  def handle_info({:EXIT, _pid, _reason}, state) do
    disconnect(state)
    {:noreply, nil}
  end
  def handle_info(_, state), do: {:noreply, state}
  def terminate(_, state), do: disconnect(state)
  defp connect(nil) do
    try do
      case AMQP.Connection.open(System.fetch_env!("AMQP_URL"), connection_timeout: 1000) do
        {:ok, connection} -> open_channel(connection)
        _ -> nil
      end
    catch
      :exit, _ -> nil
    end
  end
  defp connect(state), do: state

  defp open_channel(connection) do
    outcome =
      try do
        with {:ok, channel} <- AMQP.Channel.open(connection),
             :ok <- AMQP.Confirm.select(channel) do
          {connection, channel}
        else
          _ -> nil
        end
      catch
        :exit, _ -> nil
      end
    if outcome == nil, do: disconnect({connection, nil})
    outcome
  end
  defp disconnect(nil), do: :ok
  defp disconnect({connection, _channel}) do
    try do
      AMQP.Connection.close(connection, 250)
    catch
      :exit, _ -> :ok
    end
  end
end
