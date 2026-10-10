"""Deliberately wrong real workers; never used as candidate starting code."""

# Run this fixed source via the existing infrastructure image's `python -c`.
# It violates MAX_INFLIGHT by launching32 requests after collecting the burst.
FANOUT = r'''
import os,time,json,hashlib,urllib.request
from concurrent.futures import ThreadPoolExecutor
import pika
conn=pika.BlockingConnection(pika.URLParameters(os.environ['AMQP_URL']))
ch=conn.channel();ch.basic_qos(prefetch_count=int(os.environ['PREFETCH']))
messages=[];idle=time.monotonic()
while time.monotonic()-idle<.5 or not messages:
 method,_,body=ch.basic_get(os.environ['INPUT_QUEUE'],auto_ack=False)
 if method is None:time.sleep(.01);continue
 idle=time.monotonic();messages.append((method.delivery_tag,json.loads(body)))
def effect(pair):
 tag,e=pair
 body=dict(tenant=e['tenant'],id=e['id'],result=3*e['value']+7,digest=hashlib.sha256(e['payload'].encode()).hexdigest())
 with urllib.request.urlopen(urllib.request.Request(os.environ['SINK_URL'],data=json.dumps(body).encode(),headers={'Content-Type':'application/json'}),timeout=5) as response:
  assert response.status in (200,201)
 return tag
with ThreadPoolExecutor(max_workers=32) as pool:
 for tag in pool.map(effect,messages):ch.basic_ack(tag)
while True:conn.process_data_events(time_limit=.1)
'''
