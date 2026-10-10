require 'bundler/setup'
require 'rails'
require 'active_model/railtie'
require 'active_job/railtie'
require 'action_controller/railtie'
module QueueBenchmark
  class Application < Rails::Application
    config.load_defaults 8.1
    config.eager_load = false
    config.secret_key_base = 'benchmark-public-non-web-application-key'
    config.logger = Logger.new($stderr)
    config.paths['tmp'] = '/tmp'
    config.paths['log'] = '/tmp/rails.log'
    config.cache_store = :memory_store
  end
end
