require 'bunny'
require 'json'
require 'digest'
require 'net/http'
require 'timeout'
require 'logger'
require_relative 'handler_fault'

# The plain Ruby control and Rails arm deliberately share this delivery policy.
class QueueWorker
  def initialize(executor: ->(&block) { block.call })
    @executor = executor
    @prefetch = Integer(ENV.fetch('PREFETCH', '32'))
    @inflight = Integer(ENV.fetch('MAX_INFLIGHT', '8'))
    @timeout = Integer(ENV.fetch('REQUEST_TIMEOUT_MS', '1000')) / 1000.0
    @attempts = Integer(ENV.fetch('MAX_ATTEMPTS', '3'))
    @delay = Integer(ENV.fetch('RETRY_DELAY_MS', '100')) / 1000.0
    raise 'invalid limits' unless [@prefetch, @inflight, @timeout, @attempts, @delay].all?(&:positive?)
    @sink = URI(ENV.fetch('SINK_URL'))
    @publish_lock = Mutex.new
    @stopping = false
  end

  def run
    # Immediate process exit closes TCP, returning every unacknowledged delivery.
    # No drain promise: the evaluator may restart this worker to finish the queue.
    Signal.trap('TERM') { exit! 0 }
    Signal.trap('INT') { exit! 0 }
    loop do
      begin
        connection = Bunny.new(ENV.fetch('AMQP_URL'), automatically_recover: true,
                               network_recovery_interval: 1, heartbeat: 5,
                               connection_timeout: 2, continuation_timeout: 3000,
                               logger: Logger.new($stderr, level: Logger::WARN))
        connection.start
        @consumer = connection.create_channel(nil, @inflight, false, 5)
        @consumer.prefetch(@prefetch)
        @publisher = connection.create_channel
        @publisher.confirm_select
        @consumer.basic_consume(ENV.fetch('INPUT_QUEUE'), 'benchmark-worker', false) do |delivery, _properties, body|
          next if @stopping
          begin
            @executor.call { deliver(delivery.delivery_tag, body) }
          rescue StandardError => error
            # A broker failure leaves the delivery unacknowledged; Bunny restores
            # consumers, QoS and confirm mode, and rejects stale delivery tags.
            warn "delivery interrupted: #{error.class}"
            sleep @delay
            begin
              @consumer.basic_reject(delivery.delivery_tag, true)
            rescue StandardError
              # Disconnected or stale delivery: broker recovery owns redelivery.
            end
          end
        end
        sleep 0.05 until @stopping
        exit! 0
      rescue StandardError => error
        begin
          connection&.close
        rescue StandardError
          # Connection establishment can fail before a transport exists.
        end
        warn "connection unavailable: #{error.class}"
        exit! 0 if @stopping
        sleep 1
      end
    end
  end

  def deliver(tag, body)
    event = JSON.parse(body)
    effect = {tenant: event.fetch('tenant'), id: event.fetch('id'),
              result: 3 * event.fetch('value') + 7,
              digest: Digest::SHA256.hexdigest(event.fetch('payload'))}
    @attempts.times do |attempt|
      return if @stopping
      status = post(effect)
      case status
      when 200, 201
        @consumer.basic_ack(tag)
        return
      when 422
        @publish_lock.synchronize do
          @publisher.basic_publish(body, '', ENV.fetch('DLQ_QUEUE'), persistent: true,
                                   content_type: 'application/json')
          confirmed = Timeout.timeout(@timeout) { @publisher.wait_for_confirms }
          raise 'DLQ publication not confirmed' unless confirmed
          @consumer.basic_ack(tag)
        end
        return
      when nil, 503
        sleep @delay if attempt + 1 < @attempts
      else
        break
      end
    end
    sleep @delay
    @consumer.basic_reject(tag, true) unless @stopping
  end

  def post(effect)
    Timeout.timeout(@timeout) do
      http = Net::HTTP.new(@sink.host, @sink.port, nil)
      http.open_timeout = http.read_timeout = http.write_timeout = @timeout
      http.max_retries = 0
      request = Net::HTTP::Post.new(@sink.request_uri, 'Content-Type' => 'application/json')
      request.body = JSON.generate(effect)
      response = http.start { |client| client.request(request) }
      HandlerFaultHook.check!(response)
      response.code.to_i
    end
  rescue Timeout::Error, IOError, EOFError, SystemCallError, Net::HTTPBadResponse
    nil
  end
end
