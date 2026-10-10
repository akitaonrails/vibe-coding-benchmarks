"""Private SQLite effect ledger. Only /effects is network-visible."""
import hashlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import socket
import sqlite3
import threading
import time

ROOT = Path('/state')
LOCK = threading.RLock()
CURRENT = 0
PEAK = 0
MANIFEST = {(e['tenant'], e['id']): e for e in json.loads((ROOT/'manifest.json').read_text())}
DB = sqlite3.connect(ROOT/'sink.sqlite', check_same_thread=False)
DB.execute('PRAGMA journal_mode=WAL')
DB.execute('PRAGMA synchronous=FULL')
DB.executescript('''CREATE TABLE IF NOT EXISTS effects(tenant TEXT,id TEXT,body TEXT,committed REAL,PRIMARY KEY(tenant,id));
CREATE TABLE IF NOT EXISTS attempts(n INTEGER PRIMARY KEY,tenant TEXT,id TEXT,started REAL,finished REAL,status INTEGER,dropped INTEGER DEFAULT 0,fault_header TEXT);
CREATE TABLE IF NOT EXISTS metrics(name TEXT PRIMARY KEY,value INTEGER);''')
DB.commit()

def control():
    return json.loads((ROOT/'control.json').read_text())

def expected(e):
    return dict(tenant=e['tenant'],id=e['id'],result=3*e['value']+7,digest=hashlib.sha256(e['payload'].encode()).hexdigest())

class Handler(BaseHTTPRequestHandler):
    def log_message(self,*args):
        pass
    def do_POST(self):
        global CURRENT,PEAK
        if self.path!='/effects':
            self.send_error(404);return
        size=int(self.headers.get('Content-Length','0'))
        if not 0<size<=262144:
            self.send_error(413);return
        try:
            body=json.loads(self.rfile.read(size))
            key=(body.get('tenant'),body.get('id'))
            if any(type(part) is not str for part in key):raise ValueError('identity must be strings')
        except (ValueError,AttributeError):
            self.send_error(400);return
        with LOCK:
            CURRENT+=1;PEAK=max(PEAK,CURRENT)
            DB.execute('INSERT OR REPLACE INTO metrics VALUES (?,?)',('peak_inflight',PEAK))
            cursor=DB.execute('INSERT INTO attempts(tenant,id,started) VALUES(?,?,?)',(*key,time.time()))
            number=cursor.lastrowid;DB.commit()
        status=500;drop=False;fault_header=None;counted=True
        try:
            e=MANIFEST.get(key)
            mode=control()
            if mode.get('mode')=='blocked':
                # Every request admitted while blocked is guaranteed NOT to commit,
                # even if the worker dies and the controller releases the gate.
                until=time.monotonic()+3
                while control().get('mode')=='blocked' and time.monotonic()<until:
                    time.sleep(.02)
                status=503
            elif mode.get('mode')=='unavailable':
                status=503
            else:
                time.sleep(mode.get('delay_ms',0)/1000)
                if e is not None and e['poison']:
                    status=422
                elif e is None or body!=expected(e) or type(body.get('result')) is not int:
                    status=409
                else:
                    with LOCK:
                        issued=DB.execute("SELECT value FROM metrics WHERE name='handler_fault_issued'").fetchone()
                        if mode.get('mode')=='handler_crash' and list(key)==mode.get('fault_key') and not issued:
                            DB.execute("INSERT INTO metrics VALUES('handler_fault_issued',1)");DB.commit()
                            fault_header='handler-crash'
                    encoded=json.dumps(body,sort_keys=True,separators=(',',':'))
                    with LOCK:
                        prior=DB.execute('SELECT body FROM effects WHERE tenant=? AND id=?',key).fetchone()
                        if fault_header:
                            status=503
                        elif prior and prior[0]!=encoded:
                            status=409
                        elif prior:
                            status=200
                        else:
                            DB.execute('INSERT INTO effects VALUES(?,?,?,?)',(*key,encoded,time.time()))
                            DB.commit();status=201
                            drop=mode.get('mode')=='drop_response'
            with LOCK:
                DB.execute('UPDATE attempts SET finished=?,status=?,dropped=?,fault_header=? WHERE n=?',(time.time(),status,int(drop),fault_header,number));DB.commit()
                # Processing completes before exposing its HTTP response. Otherwise
                # the client can start a successor while this finished handler
                # waits to decrement, falsely inflating client concurrency.
                CURRENT-=1;counted=False
            if drop:
                self.close_connection=True
                try:self.connection.shutdown(socket.SHUT_RDWR)
                except OSError:pass
                return
            payload=json.dumps({'status':status}).encode()
            self.send_response(status);self.send_header('Content-Length',str(len(payload)))
            if fault_header:self.send_header('X-Langbench-Fault',fault_header)
            self.end_headers()
            try:self.wfile.write(payload)
            except (BrokenPipeError,ConnectionResetError):pass
        finally:
            with LOCK:
                if counted:CURRENT-=1

ThreadingHTTPServer(('0.0.0.0',8080),Handler).serve_forever()
