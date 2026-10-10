module Domain
  def self.key(id) = id
  def self.view(record)
    out = {'id'=>record['id'], 'status'=>{'pending'=>'pending','ready'=>'ok','failed'=>'error','cancelled'=>'error'}.fetch(record['state'])}
    out['value'] = record['payload'] if record.key?('payload')
    out
  end
  def self.decode(stored)
    out = {'id'=>stored['id'],'state'=>{'pending'=>'pending','ok'=>'ready','error'=>'failed'}.fetch(stored['status']),'generation'=>1}
    out['payload'] = stored['value'] if stored.key?('value')
    out['reason'] = 'legacy_error' if out['state'] == 'failed'
    out
  end
end
