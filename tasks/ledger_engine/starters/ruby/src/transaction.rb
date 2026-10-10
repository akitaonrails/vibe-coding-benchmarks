module Ledger
  class Transaction
    attr_reader :tenant, :revision, :writes

    def initialize(tenant, revision, table)
      @tenant = tenant
      @revision = revision
      @snapshot = table.snapshot
      @writes = {}
    end

    def read(identifier)
      Ledger.copy(@writes.key?(identifier) ? @writes[identifier] : @snapshot.row(@tenant, identifier))
    end

    def put(identifier, row)
      @writes[identifier] = Ledger.copy(row)
    end

    def overlay(table = @snapshot, revision = @revision)
      result = table.snapshot
      @writes.each { |identifier, row| result.write(@tenant, identifier, row, revision) }
      result
    end

    def scan(lower, upper)
      return [] if lower >= upper
      overlay.live_rows(@tenant).select { |row| lower <= row.fetch('id') && row.fetch('id') < upper }
    end

    def lookup(name)
      overlay.live_rows(@tenant).select { |row| row['alias'].is_a?(String) && row['alias'] == name }
    end

    def frames(request, revision)
      result = [{ 'kind' => 'BEGIN', 'tenant' => @tenant, 'request' => request, 'revision' => revision, 'count' => @writes.size }]
      @writes.keys.sort.each do |identifier|
        result << { 'kind' => 'EDIT', 'id' => identifier, 'row' => Ledger.copy(@writes.fetch(identifier)) }
      end
      result << { 'kind' => 'SEAL', 'revision' => revision }
    end
  end
end
