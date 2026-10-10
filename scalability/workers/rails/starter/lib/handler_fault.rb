# Frozen benchmark fault hook: do not rescue inside the HTTP retry routine.
module HandlerFaultHook
  class InjectedHandlerFailure < StandardError; end
  def self.check!(response)
    return unless response['X-Langbench-Fault'] == 'handler-crash'
    warn 'langbench_handler_fault: raising InjectedHandlerFailure'
    raise InjectedHandlerFailure, 'supplied work-item handler crash'
  end
end
