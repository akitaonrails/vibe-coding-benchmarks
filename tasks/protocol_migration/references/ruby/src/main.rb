require 'json'
require_relative 'solution'
STDOUT.sync = true
service = Solution.new
STDIN.each_line { |line| puts JSON.generate(service.call(JSON.parse(line))) }
