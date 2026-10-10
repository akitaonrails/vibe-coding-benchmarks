"""Trusted confirmed publisher/dead-letter observer, invoked only by controller."""
import json
import os
import sys
import time
import pika


def connect():
    return pika.BlockingConnection(pika.URLParameters(os.environ['AMQP_ADMIN_URL']))

def main():
    command=sys.argv[1]
    conn=connect();ch=conn.channel()
    if command=='setup':
        for queue in ('work','dead'):
            ch.queue_declare(queue=queue,durable=True,arguments={'x-max-length-bytes':67108864,'x-overflow':'reject-publish'})
        output={'ready':True}
    elif command=='publish':
        events=json.load(sys.stdin);rate=float(sys.argv[2]);ch.confirm_delivery()
        accepted=[];lags=[];started=time.monotonic();started_wall=time.time();uncertain=[];schedule=[]
        for index,e in enumerate(events):
            target=started+(index/rate if rate else 0)
            if target>time.monotonic():time.sleep(target-time.monotonic())
            lags.append(max(0,time.monotonic()-target))
            encoded=json.dumps(e,separators=(',',':')).encode()
            for attempt in range(3):
                try:
                    ch.basic_publish(exchange='',routing_key='work',body=encoded,properties=pika.BasicProperties(delivery_mode=2,content_type='application/json'),mandatory=True)
                    accepted.append([e['tenant'],e['id']]);schedule.append({'tenant':e['tenant'],'id':e['id'],'scheduled':started_wall+(index/rate if rate else 0),'confirmed':time.time()});break
                except (pika.exceptions.AMQPError,OSError) as exc:
                    uncertain.append({'key':[e['tenant'],e['id']],'attempt':attempt,'error':type(exc).__name__})
                    if attempt==2:raise
                    try:conn.close()
                    except Exception:pass
                    conn=connect();ch=conn.channel();ch.confirm_delivery()
        output={'accepted':accepted,'uncertain_confirms':uncertain,'publish_seconds':time.monotonic()-started,'schedule_lag_seconds':lags,'scheduled_publications':schedule,'started_at':started_wall,'finished_at':time.time()}
    elif command=='dead':
        output=[]
        while True:
            method,_,body=ch.basic_get('dead',auto_ack=False)
            if method is None:break
            try:output.append(json.loads(body))
            except ValueError:output.append({'invalid_body':body[:100].decode(errors='replace')})
            ch.basic_ack(method.delivery_tag)
    else:
        output={name:ch.queue_declare(queue=name,passive=True).method.message_count for name in ('work','dead')}
    conn.close();print(json.dumps(output))

if __name__=='__main__':main()
