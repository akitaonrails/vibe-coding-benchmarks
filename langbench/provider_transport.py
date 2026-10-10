"""Fixed-destination subscription recorder; never an arbitrary forwarding proxy."""
import http.server
import json
import threading
import time
import urllib.error
import urllib.request

MAX_BODY=16*1024*1024
ENDPOINTS={'kimi':'https://api.kimi.com/coding/v1/chat/completions',
           'opencode':'https://api.z.ai/api/coding/paas/v4/chat/completions'}


def inspect_request(provider,body,effort,tool):
    expected='k3' if provider=='kimi' else 'glm-5.3'
    if body.get('model')!=expected:raise ValueError('unexpected wire model')
    actual=(body.get('thinking') or {}).get('effort') if provider=='kimi' else body.get('reasoning_effort')
    if provider=='kimi' and (body.get('thinking') or {}).get('type')!='enabled':raise ValueError('unexpected or absent wire effort')
    if actual!=effort:raise ValueError('unexpected or absent wire effort')
    names=[]
    for entry in body.get('tools',[]):
        if entry.get('type')!='function':raise ValueError('unexpected tool type')
        name=entry.get('function',{}).get('name');names.append(name)
        if name!=tool:raise ValueError('unexpected exposed tool')
    return {'model':expected,'reasoning_effort':actual,'tool_names':names,'stream':body.get('stream')}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('subscription redirects forbidden')


class Transport:
    def __init__(self,provider,effort,tool,*,opener=None):
        if provider not in ENDPOINTS:raise ValueError('unsupported subscription')
        self.provider=provider;self.effort=effort;self.tool=tool;self.records=[];self.rejections=[];self.fatal=None;self.responses=[]
        self.condition=threading.Condition();self.active=0;self.accepting=True;self.rate_latched=False
        self.opener=opener or urllib.request.build_opener(urllib.request.ProxyHandler({}),NoRedirect())
        owner=self
        class Handler(http.server.BaseHTTPRequestHandler):
            protocol_version='HTTP/1.0'
            def log_message(self,*args):pass
            def do_POST(self):
                with owner.condition:
                    if not owner.accepting:self.send_error(503);return
                    owner.active+=1
                try:self.handle_post()
                finally:
                    with owner.condition:owner.active-=1;owner.condition.notify_all()
            def handle_post(self):
                try:
                    if self.path!='/chat/completions':raise ValueError('unexpected subscription path')
                    length=int(self.headers.get('Content-Length','-1'))
                    if not 0<length<=MAX_BODY or self.headers.get('Transfer-Encoding'):raise ValueError('invalid request framing')
                    self.connection.settimeout(130)
                    data=self.rfile.read(length)
                    if len(data)!=length:raise ValueError('incomplete request')
                    body=json.loads(data)
                    try:evidence=inspect_request(owner.provider,body,owner.effort,owner.tool)
                    except ValueError as rejection:
                        owner.rejections.append({'reason':str(rejection),'model':body.get('model'),'reasoning_effort':body.get('reasoning_effort'),'tool_names':[e.get('function',{}).get('name') for e in body.get('tools',[])],'upstream_sent':False})
                        raise
                    evidence.update(index=len(owner.records),started_at=time.time(),usage=[],response_ids=[])
                    owner.records.append(evidence)
                    if owner.rate_latched:
                        evidence.update(http_status=429,upstream_sent=False,quota_retry_blocked=True,response_complete=True)
                        self.send_error(429,'Previous subscription limit; upstream retry blocked');return
                    evidence['upstream_sent']=True
                    headers={key:value for key,value in self.headers.items() if key.lower() not in ('host','connection','content-length','transfer-encoding','proxy-authorization','proxy-connection')}
                    request=urllib.request.Request(ENDPOINTS[owner.provider],data=data,headers=headers,method='POST')
                    try:response=owner.opener.open(request,timeout=125)
                    except urllib.error.HTTPError as error:response=error
                    owner.responses.append(response)
                    with response:
                        evidence['http_status']=response.status
                        if response.status==429:owner.rate_latched=True
                        self.send_response(response.status)
                        self.send_header('Content-Type',response.headers.get('Content-Type','application/json'))
                        self.send_header('Connection','close');self.end_headers()
                        pending=b'';count=0
                        while True:
                            chunk=response.read1(65536) if hasattr(response,'read1') else response.read(65536)
                            if not chunk:break
                            count+=len(chunk)
                            if count>MAX_BODY:raise ValueError('response exceeds bound')
                            self.wfile.write(chunk);self.wfile.flush();pending+=chunk
                            while b'\n' in pending:
                                line,pending=pending.split(b'\n',1);owner.observe(evidence,line)
                        if pending:owner.observe(evidence,pending)
                        evidence['response_complete']=True
                except Exception as error:
                    # Do not serialize exception messages: urllib/provider errors may include credentials.
                    if isinstance(error,ValueError):
                        owner.fatal=str(error) if str(error) in ('unexpected wire model','unexpected or absent wire effort','unexpected tool type','unexpected exposed tool','unexpected subscription path','invalid request framing','incomplete request','response exceeds bound') else 'invalid transport data'
                    elif 'evidence' in locals():
                        evidence['transport_error']=type(error).__name__
                    try:self.send_error(502,'Subscription transport validation failed')
                    except OSError:pass
            def do_GET(self):self.send_error(405)
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.server.daemon_threads=True
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
        self.base_url='http://127.0.0.1:'+str(self.server.server_port)

    def observe(self,record,line):
        line=line.strip()
        if line.startswith(b'data:'):line=line[5:].strip()
        if not line or line==b'[DONE]':return
        try:value=json.loads(line)
        except ValueError:return
        if not isinstance(value,dict):return
        identity=value.get('id')
        if isinstance(identity,str) and identity not in record['response_ids']:record['response_ids'].append(identity)
        usage=value.get('usage')
        if usage is None and isinstance(value.get('choices'),list) and value['choices']:usage=value['choices'][0].get('usage')
        if isinstance(usage,dict):record['usage'].append(usage)

    def settle(self,timeout=15):
        with self.condition:
            self.accepting=False
            if not self.condition.wait_for(lambda:self.active==0,timeout):
                raise RuntimeError('provider request did not settle')

    def close(self):
        import socket
        for response in self.responses:
            try:
                sock=getattr(getattr(getattr(response,'fp',None),'raw',None),'_sock',None)
                if sock is not None:sock.shutdown(socket.SHUT_RDWR)
                response.close()
            except OSError:pass
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        self.settle(timeout=15)
