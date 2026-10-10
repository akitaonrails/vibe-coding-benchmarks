module Worker
  def self.apply(record, request)
    return 'not_found' unless record
    case request['op']
    when 'complete'
      return 'conflict' unless record['state'] == 'pending'
      record.delete('payload')
      if request.key?('reason')
        record['state'] = 'failed'
        record['reason'] = request['reason']
      else
        record['state'] = 'ready'
        record['payload'] = request['payload'] if request.key?('payload')
      end
    when 'cancel'
      return nil if record['state'] == 'cancelled'
      return 'conflict' unless ['pending','cancelled'].include?(record['state'])
      record['state'] = 'cancelled'
      record.delete('payload')
    when 'retry'
      return 'conflict' unless ['failed','cancelled'].include?(record['state'])
      record['state'] = 'pending'
      record['generation'] += 1
      record.delete('payload'); record.delete('reason')
    end
    nil
  end
end
