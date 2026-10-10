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

    # Tombstones participate in serializable interval validation.
    def interval_versions(tenant, lower, upper)
      @entries.each_with_object({}) do |((owner, identifier), entry), result|
        result[identifier] = entry.fetch('version') if owner == tenant && lower <= identifier && identifier < upper
      end
    end

    def alias_versions(tenant, name)
      live_rows(tenant).each_with_object({}) do |row, result|
        result[row.fetch('id')] = version(tenant, row.fetch('id')) if row['alias'].is_a?(String) && row['alias'] == name
      end
    end

    def unique_aliases?
      seen = {}
      @entries.each do |(tenant, identifier), entry|
        row = entry.fetch('row')
        next if row.nil? || !row['alias'].is_a?(String)
        key = [tenant, row['alias']]
        return false if seen.key?(key)
        seen[key] = identifier
      end
      true
    end

    def image_entries
      @entries.keys.sort.map do |tenant, identifier|
        entry = @entries.fetch([tenant, identifier])
        { 'tenant' => tenant, 'id' => identifier, 'version' => entry.fetch('version'), 'row' => Ledger.copy(entry.fetch('row')) }
      end
    end
  end
end
