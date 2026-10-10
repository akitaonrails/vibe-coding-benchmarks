require 'bundler/setup'
require_relative 'lib/worker'
QueueWorker.new.run
