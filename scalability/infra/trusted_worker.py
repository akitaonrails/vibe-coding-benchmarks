"""Infrastructure reference/mutants only; never an ecosystem treatment arm."""
import hashlib
import json
import os
import signal
import time
import urllib.error
import urllib.request
import pika

class HandlerCrash(Exception):
    pass

STOP=False
MODE=os.environ.get('MUTANT','')
def stop(*_):
    global STOP
    STOP=True
signal.signal(signal.SIGTERM,stop)

def run():
    while not STOP:
        conn=None
        try:
            conn=pika.BlockingConnection(pika.URLParameters(os.environ['AMQP_URL']))
            ch=conn.channel();ch.basic_qos(prefetch_count=int(os.environ['PREFETCH']));ch.confirm_delivery()
            while not STOP:
                method,_,body=ch.basic_get(os.environ['INPUT_QUEUE'],auto_ack=False)
                if method is None:
                    conn.process_data_events(time_limit=.03);continue
                event=json.loads(body)
                if MODE=='early_ack':ch.basic_ack(method.delivery_tag)
                effect=dict(tenant=event['tenant'],id=event['id'],result=3*event['value']+7,digest=hashlib.sha256(event['payload'].encode()).hexdigest())
                if MODE=='wrong_effect':effect['result']+=1
                done=False
                for attempt in range(int(os.environ['MAX_ATTEMPTS'])):
                    try:
                        req=urllib.request.Request(os.environ['SINK_URL'],data=json.dumps(effect).encode(),headers={'Content-Type':'application/json'})
                        with urllib.request.urlopen(req,timeout=int(os.environ['REQUEST_TIMEOUT_MS'])/1000) as response:
                            status=response.status
                            if response.headers.get('X-Langbench-Fault')=='handler-crash':
                                print('LANGBENCH_HANDLER_CRASH: raising HandlerCrash',flush=True);raise HandlerCrash()
                    except urllib.error.HTTPError as exc:
                        if exc.headers.get('X-Langbench-Fault')=='handler-crash':
                            print('LANGBENCH_HANDLER_CRASH: raising HandlerCrash',flush=True);raise HandlerCrash()
                        status=exc.code
                    except (OSError,TimeoutError):status=503
                    if status in (200,201):done=True;break
                    if status==422 and MODE!='poison_loop':
                        ch.basic_publish(exchange='',routing_key=os.environ['DLQ_QUEUE'],body=body,properties=pika.BasicProperties(delivery_mode=2),mandatory=True)
                        done=True;break
                    time.sleep(int(os.environ['RETRY_DELAY_MS'])/1000)
                    if STOP:break
                if MODE!='early_ack':
                    if done:ch.basic_ack(method.delivery_tag)
                    else:ch.basic_nack(method.delivery_tag,requeue=True)
            conn.close()
        except HandlerCrash:
            print('LANGBENCH_HANDLER_CRASH: outer handler recovery and channel requeue',flush=True)
            time.sleep(.1)
        except (pika.exceptions.AMQPError,OSError):
            if MODE=='no_reconnect':return
            time.sleep(.2)
        finally:
            if conn is not None and conn.is_open:
                try:conn.close()
                except Exception:pass

if __name__=='__main__':run()
