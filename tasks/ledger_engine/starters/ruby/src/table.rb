module Ledger
  class Table
    attr_reader :entries

    def initialize(entries = {})
      @entries = Ledger.copy(entries)
    end

    def snapshot
      Table.new(@entries)
    end

    def version(tenant, identifier)
      entry = @entries[[tenant, identifier]]
      entry ? entry.fetch('version') : 0
    end

    def row(tenant, identifier)
      @entries[[tenant, identifier]]&.fetch('row')
    end

    def write(tenant, identifier, row, revision)
      @entries[[tenant, identifier]] = { 'version' => revision, 'row' => Ledger.copy(row) }
    end

    def live_rows(tenant)
      @entries.filter_map do |(owner, _), entry|
        entry.fetch('row') if owner == tenant && !entry.fetch('row').nil?
      end.sort_by { |row| row.fetch('id') }
    end

    def image_entries
      @entries.keys.sort.map do |tenant, identifier|
        entry = @entries.fetch([tenant, identifier])
        { 'tenant' => tenant, 'id' => identifier, 'version' => entry.fetch('version'), 'row' => Ledger.copy(entry.fetch('row')) }
      end
    end
  end
end
