require_relative 'domain'
require_relative 'repository'
require_relative 'worker'
class Solution
  def initialize = @repository = Repository.new
  def call(q)
    version = q.fetch('v', 1)
    return {'error'=>'unsupported_version'} unless version == 1
    key = Domain.key(q['id'])
    record = @repository.read(key)
    case q['op']
    when 'get','export'
      return {'error'=>'not_found'} unless record
      view = Domain.view(record)
      return q['op'] == 'get' ? {'record'=>view} : {'stored'=>view.merge('schema'=>version)}
    when 'submit'
      return {'error'=>'conflict'} if record
      record = {'id'=>q['id'],'state'=>'pending','generation'=>1}
      record['payload'] = q['payload'] if q.key?('payload')
    when 'import'
      stored = q['stored']
      return {'error'=>'unsupported_schema'} unless stored['schema'] == 1
      return {'error'=>'identity'} if stored['id'] != q['id']
      record = Domain.decode(stored)
    else
      error = Worker.apply(record, q)
      return {'error'=>error} if error
    end
    @repository.write(key, record)
    {'record'=>Domain.view(record)}
  end
end
