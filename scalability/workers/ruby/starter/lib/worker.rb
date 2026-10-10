require 'bunny'
require 'json'
require 'digest'
require 'net/http'
require 'logger'
require_relative 'handler_fault'

# Working clean-path transport. Complete the failure/concurrency contract.
class QueueWorker
  def initialize(executor: ->(&block) { block.call })
    @executor = executor
  end

  def run
    Signal.trap('TERM') { exit! 0 }
    connection = Bunny.new(ENV.fetch('AMQP_URL'), automatically_recover: true,
                           logger: Logger.new($stderr, level: Logger::WARN))
    connection.start
    channel = connection.create_channel
    channel.prefetch(1)
    channel.basic_consume(ENV.fetch('INPUT_QUEUE'), 'starter-worker', false) do |delivery, _properties, body|
      @executor.call do
        event = JSON.parse(body)
        effect = {tenant: event.fetch('tenant'), id: event.fetch('id'),
                  result: 3 * event.fetch('value') + 7,
                  digest: Digest::SHA256.hexdigest(event.fetch('payload'))}
        endpoint = URI(ENV.fetch('SINK_URL'))
        request = Net::HTTP::Post.new(endpoint.request_uri, 'Content-Type' => 'application/json')
        request.body = JSON.generate(effect)
        http = Net::HTTP.new(endpoint.host, endpoint.port, nil)
        http.max_retries = 0
        response = http.start { |client| client.request(request) }
        HandlerFaultHook.check!(response)
        if [200, 201].include?(response.code.to_i)
          channel.basic_ack(delivery.delivery_tag)
        else
          sleep Integer(ENV.fetch('RETRY_DELAY_MS', '100')) / 1000.0
          channel.basic_reject(delivery.delivery_tag, true)
        end
      end
    end
    sleep # Keep the worker alive while Bunny performs its normal recovery.
  end
end
