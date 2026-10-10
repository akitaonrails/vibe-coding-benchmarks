require 'json'
require_relative 'engine'
engine = Ledger::Engine.new
STDIN.each_line do |line|
  puts JSON.generate(engine.call(JSON.parse(line)))
end
