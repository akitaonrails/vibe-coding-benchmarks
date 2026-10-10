"""Single-tool MCP transport. Only the owning controller can dispatch Docker calls."""
import argparse
import hmac
import json
from pathlib import Path
import secrets
import socket
import socketserver
import sys
import threading
import time

MAX_FRAME = 1024*1024
TOOL = {'name':'sandbox_shell','description':'Execute a command in the offline candidate /workspace. Edit only src/. Background jobs are stopped when the call returns.',
        'inputSchema':{'type':'object','properties':{'command':{'type':'string'},'timeout_seconds':{'type':'integer','minimum':1,'maximum':120}},'required':['command'],'additionalProperties':False}}


def validate_arguments(arguments):
    if not isinstance(arguments,dict) or set(arguments)-{'command','timeout_seconds'}:
        return 'Expected only command and optional timeout_seconds.'
    command=arguments.get('command')
    if not isinstance(command,str) or not command or '\0' in command:
        return 'command must be a nonempty string without NUL.'
    try: encoded=command.encode('utf-8')
    except UnicodeError:return 'command must contain valid Unicode.'
    if len(encoded)>128*1024:return 'command exceeds 128 KiB.'
    timeout=arguments.get('timeout_seconds',30)
    if type(timeout) is not int or not 1<=timeout<=120:
        return 'timeout_seconds must be an integer between 1 and 120.'
    return None


class Bridge:
    def __init__(self, directory, execute, source_hash):
        self.token=secrets.token_hex(32)
        self.path=Path(directory)/'bridge.sock'
        self.records=[]
        self.execute=execute
        self.source_hash=source_hash
        self.deadline=0
        self.dispatch_lock=threading.Lock()
        self.fatal=None
        owner=self
        class Handler(socketserver.StreamRequestHandler):
            def handle(self):
                self.connection.settimeout(130)
                frame=self.rfile.readline(MAX_FRAME+1)
                try:
                    if len(frame)>MAX_FRAME:raise ValueError('oversize bridge frame')
                    request=json.loads(frame)
                    if not isinstance(request,dict) or not hmac.compare_digest(str(request.get('token','')),owner.token):
                        raise ValueError('bridge authentication failed')
                    response=owner.dispatch(request)
                except Exception as error:
                    owner.fatal=type(error).__name__+': '+str(error)
                    response={'fatal':owner.fatal}
                self.wfile.write(json.dumps(response).encode()+b'\n')
        self.server=socketserver.UnixStreamServer(str(self.path),Handler)
        self.path.chmod(0o600)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()

    def dispatch(self,request):
        with self.dispatch_lock:
            return self._dispatch(request)

    def settle(self,timeout=15):
        if not self.dispatch_lock.acquire(timeout=timeout):
            raise RuntimeError('candidate dispatch did not settle')
        self.dispatch_lock.release()

    def _dispatch(self,request):
        if request.get('name')!='sandbox_shell':raise ValueError('unapproved capability')
        if time.monotonic()>=self.deadline:raise TimeoutError('invocation deadline expired')
        args=request.get('arguments')
        error=validate_arguments(args)
        record={'call_id':request.get('call_id'),'name':'sandbox_shell','arguments':args,
                'started_at':time.time(),'rejected':bool(error),'seconds':0,'state':'started'}
        self.records.append(record)
        if error:
            record['result']={'error':error}
        else:
            before=self.source_hash()
            started=time.monotonic()
            result=self.execute(args['command'],min(args.get('timeout_seconds',30),max(.001,self.deadline-time.monotonic())))
            record.update(seconds=time.monotonic()-started,source_before=before,source_after=self.source_hash(),result=result)
        record['state']='finished'
        return {'content':[{'type':'text','text':json.dumps(record['result'])}],'isError':bool(error)}

    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)
        self.path.unlink(missing_ok=True)


def serve_stdio(socket_path,token_file):
    token=Path(token_file).read_text().strip()
    initialized=False
    while True:
        frame=sys.stdin.buffer.readline(MAX_FRAME+1)
        if not frame:break
        if len(frame)>MAX_FRAME:raise ValueError('oversize MCP frame')
        request=json.loads(frame)
        identity=request.get('id');method=request.get('method')
        with Path(token_file).with_name('mcp-protocol.jsonl').open('a') as audit:
            audit.write(json.dumps({'method':method,'id':identity})+'\n')
        if method in ('notifications/initialized','notifications/cancelled'):continue
        if identity is None:raise ValueError('unexpected MCP notification')
        if method=='initialize':
            initialized=True
            result={'protocolVersion':request.get('params',{}).get('protocolVersion','2024-11-05'),
                    'capabilities':{'tools':{}},'serverInfo':{'name':'langbench','version':'1'}}
        elif not initialized:raise ValueError('MCP used before initialization')
        elif method=='ping':result={}
        elif method=='tools/list':result={'tools':[TOOL]}
        elif method=='resources/list':result={'resources':[]}
        elif method=='resources/templates/list':result={'resourceTemplates':[]}
        elif method=='prompts/list':result={'prompts':[]}
        elif method=='tools/call':
            params=request.get('params',{})
            forwarded={**params,'token':token,'call_id':identity}
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as client:
                client.settimeout(135);client.connect(socket_path)
                client.sendall(json.dumps(forwarded).encode()+b'\n')
                with client.makefile('rb') as handle:
                    data=handle.readline(MAX_FRAME+1)
                if len(data)>MAX_FRAME:raise ValueError('oversize bridge response')
                result=json.loads(data)
                if 'fatal' in result:raise ValueError(result['fatal'])
        else:raise ValueError('unexpected MCP method: '+str(method))
        print(json.dumps({'jsonrpc':'2.0','id':identity,'result':result}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--socket',required=True);parser.add_argument('--token-file',required=True)
    args=parser.parse_args();serve_stdio(args.socket,args.token_file)
