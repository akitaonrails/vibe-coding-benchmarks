require 'set'
class Solution
  def initialize
    @data = {}; @pages = []; @allocated = Set.new; @snapshots = {}
    @next_page = 1; @next_snapshot = 1; @capacity = 0
  end
  def call(r)
    case r.fetch('op')
    when 'init'
      initialize; @capacity = r.fetch('capacity'); {'ok'=>true}
    when 'crash'
      {'ok'=>true}
    when 'status'
      {'used'=>@allocated.size, 'live'=>live.size, 'snapshots'=>@snapshots.size}
    when 'read'
      return {'data'=>@data.dup} unless r.key?('snapshot')
      s = @snapshots[r['snapshot']]
      s ? {'data'=>s[0].dup} : {'error'=>'snapshot'}
    when 'snapshot'
      id = @next_snapshot; @next_snapshot += 1
      @snapshots[id] = [@data.dup, @pages.dup]; {'snapshot'=>id}
    when 'drop'
      @snapshots.delete(r['snapshot']) ? {'ok'=>true} : {'error'=>'snapshot'}
    when 'reclaim'
      garbage = (@allocated-live).to_a.sort
      count = [r.fetch('cut',garbage.size),garbage.size].min
      garbage.take(count).each { |p| @allocated.delete(p) }
      r.key?('cut') ? {'crashed'=>true} : {'reclaimed'=>count}
    when 'commit'
      next_data = @data.dup
      r.fetch('changes').each { |k,v| v.nil? ? next_data.delete(k) : next_data[k] = v }
      n = [1,next_data.size].max
      return {'error'=>'full'} if @allocated.size+n > @capacity
      steps = r.fetch('cut',n+1)
      fresh = []
      [steps,n].min.times do
        fresh << @next_page; @allocated.add(@next_page); @next_page += 1
      end
      if steps > n
        @data = next_data; @pages = fresh
      end
      r.key?('cut') ? {'crashed'=>true} : {'ok'=>true}
    end
  end
  def live
    Set.new(@pages + @snapshots.values.flat_map { |s| s[1] })
  end
end
