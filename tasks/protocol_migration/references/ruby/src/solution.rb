require_relative 'domain'
require_relative 'repository'
require_relative 'worker'
class Solution
  def initialize = @repository = Repository.new
  def call(q)
    version = q.fetch('v', 1)
    
    tenant = version == 1 ? 'legacy' : q['tenant']
    return {'error'=>'forbidden'} if version == 2 && q['actor'] != tenant
    key = Domain.key(tenant, q['id'])
    record = @repository.read(key)
    case q['op']
    when 'get','export'
      return {'error'=>'not_found'} unless record
      view = Domain.view(record, version)
      return q['op'] == 'get' ? {'record'=>view} : {'stored'=>view.merge('schema'=>version)}
    when 'submit'
      return {'error'=>'conflict'} if record
      record = {'tenant'=>tenant,'id'=>q['id'],'state'=>'pending','generation'=>1}
      record['payload'] = q['payload'] if q.key?('payload')
    when 'import'
      stored = q['stored']
      
      return {'error'=>'identity'} if stored['id'] != q['id'] || (stored['schema'] == 2 && stored['tenant'] != tenant)
      record = Domain.decode(stored, tenant)
    else
      error = Worker.apply(record, q, version)
      return {'error'=>error} if error
    end
    @repository.write(key, record)
    {'record'=>Domain.view(record, version)}
  end
end
