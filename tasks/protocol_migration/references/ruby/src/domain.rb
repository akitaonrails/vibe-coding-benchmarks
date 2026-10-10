module Domain
  def self.key(tenant, id) = [tenant, id]
  def self.view(record, version)
    return record.dup if version == 2
    out = {'id'=>record['id'], 'status'=>{'pending'=>'pending','ready'=>'ok','failed'=>'error','cancelled'=>'error'}.fetch(record['state'])}
    out['value'] = record['payload'] if record.key?('payload')
    out
  end
  def self.decode(stored, tenant)
    return stored.reject { |k,_| k == 'schema' } if stored['schema'] == 2
    out = {'tenant'=>tenant,'id'=>stored['id'],'state'=>{'pending'=>'pending','ok'=>'ready','error'=>'failed'}.fetch(stored['status']),'generation'=>1}
    out['payload'] = stored['value'] if stored.key?('value')
    out['reason'] = 'legacy_error' if out['state'] == 'failed'
    out
  end
end
