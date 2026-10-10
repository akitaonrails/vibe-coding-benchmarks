module Ledger
  # This is the entire stable state: a published image, its legacy owner, and delta frames.
  class Device
    attr_reader :capacity, :journal, :image, :legacy_owner, :loaded

    def initialize(capacity)
      @capacity = capacity
      @image = { 'schema' => 2, 'revision' => 0, 'entries' => [], 'receipts' => [] }
      @journal = []
      @legacy_owner = nil
      @loaded = false
    end

    def space_for?(count)
      @journal.size + count <= @capacity
    end

    def append(frames, fault = nil)
      retained = Ledger.copy(fault ? frames.first(fault.fetch('keep')) : frames)
      retained[-1] = { 'kind' => 'TORN' } if fault && fault.fetch('tear') && !retained.empty?
      @journal.concat(retained)
    end

    def publish(image, fault = nil)
      return if fault && !(fault.fetch('keep') == 2 && !fault.fetch('tear'))
      @image = Ledger.copy(image)
      @legacy_owner = nil
      @journal = []
    end

    def load(image, tenant)
      @image = Ledger.copy(image)
      @legacy_owner = tenant
      @loaded = true
      @journal = []
    end

    # Validate boundaries before exposing a delta; incomplete suffixes never enter the table.
    def complete_groups
      groups = []
      position = 0
      while position < @journal.size
        header = @journal[position]
        break unless header['kind'] == 'BEGIN'
        count = header.fetch('count')
        edits = @journal.slice(position + 1, count)
        seal = @journal[position + count + 1]
        break unless edits && edits.size == count && edits.all? { |frame| frame['kind'] == 'EDIT' }
        break unless seal && seal['kind'] == 'SEAL' && seal['revision'] == header['revision']
        groups << [header, edits]
        position += count + 2
      end
      @journal = @journal.first(position)
      groups
    end

    def recover
      table = Table.new
      receipts = {}
      revision = @image.fetch('revision')
      legacy = @image.fetch('schema') == 1
      @image.fetch('entries').each do |entry|
        tenant = legacy ? @legacy_owner : entry.fetch('tenant')
        row = Ledger.copy(entry.fetch('row'))
        row['tenant'] = tenant if legacy && row
        table.write(tenant, entry.fetch('id'), row, entry.fetch('version'))
      end
      @image.fetch('receipts').each do |receipt|
        tenant = legacy ? @legacy_owner : receipt.fetch('tenant')
        receipts[[tenant, receipt.fetch('request')]] = receipt.fetch('revision')
      end
      complete_groups.each do |header, edits|
        revision = header.fetch('revision')
        tenant = header.fetch('tenant')
        edits.each { |edit| table.write(tenant, edit.fetch('id'), edit.fetch('row'), revision) }
        receipts[[tenant, header.fetch('request')]] = revision
      end
      [table, receipts, revision]
    end

    def inspect_tenant(tenant)
      image = Ledger.copy(@image)
      if image.fetch('schema') == 1
        if @legacy_owner != tenant
          image['entries'] = []
          image['receipts'] = []
        end
      else
        image['entries'].select! { |entry| entry.fetch('tenant') == tenant }
        image['receipts'].select! { |receipt| receipt.fetch('tenant') == tenant }
      end
      frames = []
      complete_groups.each do |header, edits|
        next unless header.fetch('tenant') == tenant
        frames.concat([Ledger.copy(header), *Ledger.copy(edits), { 'kind' => 'SEAL', 'revision' => header.fetch('revision') }])
      end
      { 'checkpoint' => image, 'journal' => frames }
    end
  end
end
