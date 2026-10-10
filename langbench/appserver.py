"""Bounded JSON-RPC transport for the pinned Codex app-server.

Controller credentials stay outside the Docker tool worker. Account responses are
never written to the event ledger. No API key or user configuration is inherited.
"""
from collections import deque
import json
import os
from pathlib import Path
import selectors
import select
import signal
import subprocess
import tempfile
import time

DEFAULT_BINARY = Path.home()/'.local/share/mise/installs/codex/0.156.0/bin/codex'
DISABLED_FEATURES = ('shell_tool','unified_exec','apps','plugins','multi_agent','multi_agent_v2','hooks',
    'memories','remote_plugin','browser_use','browser_use_external','browser_use_full_cdp_access',
    'computer_use','code_mode','code_mode_only','image_generation','in_app_browser','in_app_local_automation',
    'view_image','skill_search','skill_mcp_dependency_install','shell_snapshot','sleep_tool','goals',
    'tool_suggest','workspace_dependencies','worktrees')

class RpcError(RuntimeError):pass
class ProtocolViolation(RuntimeError):pass

class AppServer:
    def __init__(self, binary=DEFAULT_BINARY, auth=None):
        self.binary=Path(binary).resolve()
        if not self.binary.is_file():raise RuntimeError('pinned Codex binary unavailable')
        companion=self.binary.parent/'codex-code-mode-host'
        if not companion.is_file():raise RuntimeError('pinned Code Mode companion unavailable')
        auth=Path(auth or Path.home()/'.codex/auth.json')
        if not auth.is_file():raise RuntimeError('existing subscription sign-in unavailable')
        self.temp=tempfile.TemporaryDirectory(prefix='langbench-controller-')
        self.home=Path(self.temp.name)
        (self.home/'auth.json').symlink_to(auth.resolve())
        self.cwd=self.home/'empty';self.cwd.mkdir()
        command=[str(self.binary),'app-server','--stdio','--strict-config','-c','web_search="disabled"',
                 '-c','features.skip_host_skill_discovery=true','--enable','code_mode_host']
        for name in DISABLED_FEATURES:command+=['--disable',name]
        self.command=command
        self.proc=subprocess.Popen(command,cwd=self.cwd,env={'HOME':str(self.home),'CODEX_HOME':str(self.home),
              'PATH':str(self.binary.parent)+':/usr/bin:/bin','LANG':'C.UTF-8'},stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,
              start_new_session=True,bufsize=0)
        os.set_blocking(self.proc.stdin.fileno(),False)
        self.selector=selectors.DefaultSelector()
        for stream,name in ((self.proc.stdout,'stdout'),(self.proc.stderr,'stderr')):
            os.set_blocking(stream.fileno(),False);self.selector.register(stream,selectors.EVENT_READ,name)
        self.buffer=bytearray();self.stderr=bytearray();self.queue=deque();self.pending=deque();self.sequence=0;self.bytes=0

    def send(self, message, deadline=None):
        data=(json.dumps(message,separators=(',',':'))+'\n').encode()
        if len(data)>2*1024*1024:raise ProtocolViolation('outgoing RPC exceeds bound')
        deadline=deadline if deadline is not None else time.monotonic()+10
        pending=memoryview(data)
        while pending:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('RPC write deadline exceeded')
            self._drain(self.selector.select(0))
            if not select.select([], [self.proc.stdin.fileno()], [], min(remaining,.05))[1]:
                continue
            try:written=os.write(self.proc.stdin.fileno(),pending)
            except BlockingIOError:continue
            pending=pending[written:]

    def _drain(self, ready):
        for key,_ in ready:
            chunk=os.read(key.fd,65536)
            if not chunk:
                self.selector.unregister(key.fileobj)
                continue
            self.bytes+=len(chunk)
            if self.bytes>64*1024*1024:raise ProtocolViolation('app-server output budget exceeded')
            if key.data=='stderr':
                self.stderr.extend(chunk)
                if len(self.stderr)>1024*1024:raise ProtocolViolation('app-server stderr budget exceeded')
                continue
            self.buffer.extend(chunk)
            while b'\n' in self.buffer:
                line,_,tail=self.buffer.partition(b'\n');self.buffer=bytearray(tail)
                if len(line)>2*1024*1024:raise ProtocolViolation('RPC line exceeds bound')
                if line.strip():self.queue.append(json.loads(line))
            if len(self.buffer)>2*1024*1024:raise ProtocolViolation('unterminated RPC exceeds bound')

    def receive(self, deadline):
        while not self.queue:
            remaining=deadline-time.monotonic()
            if remaining<=0:raise TimeoutError('app-server deadline exceeded')
            ready=self.selector.select(min(remaining,.2))
            if not ready and self.proc.poll() is not None:raise RpcError('app-server exited')
            self._drain(ready)
        return self.queue.popleft()

    def call(self, method, params, timeout=30):
        self.sequence+=1;ident=self.sequence
        deadline=time.monotonic()+timeout
        self.send({'id':ident,'method':method,'params':params},deadline=deadline)
        while True:
            message=self.receive(deadline)
            if message.get('id')==ident and 'method' not in message:
                if 'error' in message:raise RpcError(f'{method} rejected: '+str(message['error'].get('code','unknown')))
                return message.get('result',{})
            self.pending.append(message)

    def next(self,deadline):return self.pending.popleft() if self.pending else self.receive(deadline)

    def initialize(self, model, effort):
        self.call('initialize',{'clientInfo':{'name':'langbench','version':'0.1.0'},'capabilities':{'experimentalApi':True}})
        self.send({'method':'initialized','params':{}})
        account=self.call('account/read',{'refreshToken':False})
        if not isinstance(account.get('account'),dict) or account['account'].get('type')!='chatgpt':raise RuntimeError('benchmark requires existing ChatGPT subscription auth')
        cursor=None;models=[]
        for _ in range(20):
            page=self.call('model/list',{'cursor':cursor,'limit':100,'includeHidden':True})
            models.extend(page.get('data',[]));cursor=page.get('nextCursor')
            if not cursor:break
        else:raise ProtocolViolation('unbounded model catalog')
        match=next((row for row in models if row.get('model')==model),None)
        if match is None or effort not in [row.get('reasoningEffort') for row in match.get('supportedReasoningEfforts',[])]:
            raise RuntimeError('exact requested model/effort not available; no fallback')
        return {'auth_mode':'chatgpt','requested_model':model,'effort':effort,'catalog_match':True}

    def close(self):
        if self.proc.poll() is None:
            try:os.killpg(self.proc.pid,signal.SIGTERM)
            except ProcessLookupError:pass
            try:self.proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                os.killpg(self.proc.pid,signal.SIGKILL);self.proc.wait()
        self.selector.close()
        for stream in (self.proc.stdin,self.proc.stdout,self.proc.stderr):stream.close()
        self.temp.cleanup()
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
