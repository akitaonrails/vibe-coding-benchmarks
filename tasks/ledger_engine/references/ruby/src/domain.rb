# Canonical values are shared by the wire, transaction and persistence layers.
module Ledger
  def self.copy(value)
    case value
    when Hash then value.to_h { |key, item| [key, copy(item)] }
    when Array then value.map { |item| copy(item) }
    when String then value.dup
    else value
    end
  end

  def self.record(tenant, identifier, request)
    result = { 'tenant' => tenant, 'id' => identifier, 'value' => request.fetch('value') }
    %w[alias note].each { |field| result[field] = copy(request[field]) if request.key?(field) }
    result
  end

  def self.wire_record(row, version)
    return nil if row.nil?
    result = copy(row)
    result.delete('tenant') if version == 1
    result
  end
end
