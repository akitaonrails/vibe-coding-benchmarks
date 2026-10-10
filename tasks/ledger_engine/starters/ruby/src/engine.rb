require_relative 'domain'
require_relative 'table'
require_relative 'transaction'
require_relative 'device'

module Ledger
  class Engine
    def initialize
      reset(64)
    end

    def reset(capacity)
      @device = Device.new(capacity)
      recover
    end

    def recover
      @table, @receipts, @revision = @device.recover
      @transactions = {}
    end

    def error(code)
      { 'error' => code }
    end

    def image
      receipts = @receipts.keys.sort.map do |tenant, request|
        { 'tenant' => tenant, 'request' => request, 'revision' => @receipts.fetch([tenant, request]) }
      end
      { 'schema' => 2, 'revision' => @revision, 'entries' => @table.image_entries, 'receipts' => receipts }
    end

    def pristine?
      @revision.zero? && @transactions.empty? && @device.image.fetch('entries').empty? &&
        @device.image.fetch('receipts').empty? && @device.journal.empty? && !@device.loaded
    end

    def checkpoint(request)
      return error('unsupported_fault') if request.key?('fault')
      @device.publish(image)
      { 'checkpoint' => @revision }
    end

    def commit(request, tenant)
      identity = [tenant, request.fetch('request')]
      transaction = @transactions[request['tx']]
      return error('transaction_missing') unless transaction
      return error('transaction_owner') unless transaction.tenant == tenant
      return error('unsupported_fault') if request.key?('fault')
      next_revision = @revision + 1
      proposed = transaction.overlay(@table, next_revision)
      frames = transaction.frames(request.fetch('request'), next_revision)
      return error('capacity') unless @device.space_for?(frames.size)
      @device.append(frames)
      @table = proposed
      @revision = next_revision
      @receipts[identity] = @revision
      @transactions.delete(request.fetch('tx'))
      { 'committed' => @revision }
    end

    def call(request)
      op = request.fetch('op')
      case op
      when 'init'
        reset(request.fetch('capacity'))
        return { 'ok' => true }
      when 'stats'
        return { 'revision' => @revision, 'journal_frames' => @device.journal.size, 'capacity' => @device.capacity, 'transactions' => @transactions.size }
      when 'crash'
        recover
        return { 'recovered' => @revision }
      when 'checkpoint'
        return checkpoint(request)
      end
      version = request.fetch('v', 1)
      return error('unsupported_version') if version != 1
      tenant = 'legacy'
      case op
      when 'inspect'
        return @device.inspect_tenant(tenant)
      when 'load'
        return error('not_empty') unless pristine?
        @device.load(request.fetch('image'), tenant)
        recover
        return { 'loaded' => @revision }
      when 'begin'
        return error('transaction_exists') if @transactions.key?(request.fetch('tx'))
        @transactions[request.fetch('tx')] = Transaction.new(tenant, @revision, @table)
        return { 'snapshot' => @revision }
      when 'commit'
        return commit(request, tenant)
      end
      transaction = @transactions[request.fetch('tx')]
      return error('transaction_missing') unless transaction
      return error('transaction_owner') unless transaction.tenant == tenant
      case op
      when 'read'
        { 'record' => Ledger.wire_record(transaction.read(request.fetch('id')), version) }
      when 'scan'
        { 'records' => transaction.scan(request.fetch('lo'), request.fetch('hi')).map { |row| Ledger.wire_record(row, version) } }
      when 'lookup'
        { 'records' => transaction.lookup(request.fetch('alias')).map { |row| Ledger.wire_record(row, version) } }
      when 'put'
        transaction.put(request.fetch('id'), Ledger.record(tenant, request.fetch('id'), request))
        { 'ok' => true }
      when 'delete'
        transaction.put(request.fetch('id'), nil)
        { 'ok' => true }
      when 'abort'
        @transactions.delete(request.fetch('tx'))
        { 'ok' => true }
      end
    end
  end
end
