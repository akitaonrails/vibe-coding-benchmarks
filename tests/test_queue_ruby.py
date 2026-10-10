"""Delivery-policy unit tests; real broker/container tests remain authoritative."""
import pathlib
import shutil
import subprocess
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]

@unittest.skipUnless(shutil.which('ruby'), 'Ruby is required')
class RubyQueuePolicyTests(unittest.TestCase):
    def test_native_delivery_policy(self):
        script = r'''
require 'json'
# The transport is a fake here; no Bunny installation or broker is required.
$LOADED_FEATURES << 'bunny.rb'
require ARGV.fetch(0)
ENV['SINK_URL']='http://sink:8080/effects'
ENV['DLQ_QUEUE']='dead'
class Policy < QueueWorker
  attr_reader :events
  def initialize(statuses, confirmed=true)
    super()
    @statuses=statuses;@confirmed=confirmed;@events=[]
    @consumer=@publisher=self
  end
  def post(effect); @events << ['post',effect];@statuses.shift;end
  def sleep(delay);@events << ['delay',delay];end
  def basic_ack(tag);@events << ['ack',tag];end
  def basic_reject(tag,requeue);@events << ['reject',tag,requeue];end
  def basic_publish(body,exchange,queue,**options);@events << ['publish',JSON.parse(body),exchange,queue,options];end
  def wait_for_confirms;@events << ['confirm'];@confirmed;end
end
body=JSON.generate(tenant:'a',id:'same',value:-3,payload:'abc',poison:false)
worker=Policy.new([503,nil,201]);worker.deliver(7,body)
raise 'retry order' unless worker.events.map(&:first)==%w[post delay post delay post ack]
raise 'transformation' unless worker.events.first[1]=={tenant:'a',id:'same',result:-2,digest:Digest::SHA256.hexdigest('abc')}
worker=Policy.new([503,503,503]);worker.deliver(7,body)
raise 'exhaustion' unless worker.events.map(&:first)==%w[post delay post delay post delay reject]
worker=Policy.new([409]);worker.deliver(7,body)
raise 'conflict ack/hot loop' unless worker.events.map(&:first)==%w[post delay reject]
worker=Policy.new([422]);worker.deliver(7,body)
raise 'DLQ ack ordering' unless worker.events.map(&:first)==%w[post publish confirm ack]
publication=worker.events[1]
raise 'DLQ original/persistent' unless publication[1]==JSON.parse(body) && publication[2]=='' && publication[3]=='dead' && publication[4][:persistent]
worker=Policy.new([422],false)
begin
 worker.deliver(7,body)
 raise 'missing confirmation accepted'
rescue RuntimeError=>error
 raise unless error.message=='DLQ publication not confirmed'
end
raise 'negative confirmation ack' if worker.events.any? { |e|e.first=='ack' }
class FakeHTTP
 attr_accessor :open_timeout, :read_timeout, :write_timeout, :max_retries
 def start;yield self;end
 def request(_)
  response=Net::HTTPServiceUnavailable.new('1.1','503','Unavailable')
  response['X-Langbench-Fault']='handler-crash'
  response
 end
end
class << Net::HTTP
 alias original_new new
 def new(*);FakeHTTP.new;end
end
begin
 QueueWorker.new.post({})
 raise 'handler hook swallowed into HTTP retry'
rescue HandlerFaultHook::InjectedHandlerFailure
 # The outer delivery boundary, not the HTTP transport retry, must handle this.
ensure
 class << Net::HTTP
  alias new original_new
 end
end
'''
        worker = ROOT/'scalability/workers/ruby/reference/lib/worker.rb'
        completed = subprocess.run(['ruby', '-e', script, str(worker)], capture_output=True, text=True, timeout=10)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def test_framework_control_has_identical_policy_and_actual_rails_boot(self):
        workers = ROOT/'scalability/workers'
        self.assertEqual((workers/'ruby/reference/lib/worker.rb').read_bytes(), (workers/'rails/reference/lib/worker.rb').read_bytes())
        main = (workers/'rails/reference/main.rb').read_text()
        self.assertIn('Rails.application.initialize!', main)
        self.assertIn('Rails.application.executor.wrap', main)
