require_relative 'config/application'
Rails.application.initialize!
require_relative 'lib/worker'
warn "Rails #{Rails.version} application initialized"
QueueWorker.new(executor: ->(&block) { Rails.application.executor.wrap(&block) }).run
