class Repository
  def initialize
    @rows = {}
    @cache = {}
  end
  def read(key)
    @cache[key] = @rows[key]&.dup unless @cache.key?(key)
    @cache[key]&.dup
  end
  def write(key, record)
    @rows[key] = record.dup
    @cache.delete(key)
  end
end
