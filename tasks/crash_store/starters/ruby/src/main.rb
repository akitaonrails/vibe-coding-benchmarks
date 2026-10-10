require 'json'
require_relative 'solution'
STDOUT.sync = true
solution = Solution.new
STDIN.each_line { |line| puts JSON.generate(solution.call(JSON.parse(line))) }
