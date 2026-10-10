"""Bounded process output and process-group cleanup, including orphaned children."""
import os
import selectors
import resource
import signal
import subprocess
import time

def _limits():
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_FSIZE, (256*1024*1024, 256*1024*1024))
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    resource.setrlimit(resource.RLIMIT_AS, (4*1024**3, 4*1024**3))

def execute(argv, *, cwd=None, stdin='', timeout=30, env=None, output_limit=4*1024*1024):
    started = time.monotonic()
    proc = subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, start_new_session=True, preexec_fn=_limits)
    sel = selectors.DefaultSelector()
    buffers = {'stdout': bytearray(), 'stderr': bytearray()}
    for name in buffers:
        stream = getattr(proc, name)
        os.set_blocking(stream.fileno(), False)
        sel.register(stream, selectors.EVENT_READ, name)
    pending = memoryview(stdin.encode())
    os.set_blocking(proc.stdin.fileno(), False)
    if pending:
        sel.register(proc.stdin, selectors.EVENT_WRITE, 'stdin')
    else:
        proc.stdin.close()
    reason = None
    try:
        while sel.get_map():
            if time.monotonic() - started >= timeout:
                reason = 'timeout'
                break
            for key, _ in sel.select(min(.1, max(.001, timeout - (time.monotonic()-started)))):
                if key.data == 'stdin':
                    try:
                        count = os.write(key.fd, pending[:65536])
                        pending = pending[count:]
                    except BrokenPipeError:
                        pending = memoryview(b'')
                    if not pending:
                        sel.unregister(key.fileobj)
                        key.fileobj.close()
                    continue
                chunk = os.read(key.fd, 65536)
                if not chunk:
                    sel.unregister(key.fileobj)
                    continue
                buffers[key.data].extend(chunk)
                if sum(map(len, buffers.values())) > output_limit:
                    reason = 'output_limit'
                    break
            if reason:
                break
        if reason is None:
            try:
                proc.wait(timeout=max(.001, timeout-(time.monotonic()-started)))
            except subprocess.TimeoutExpired:
                reason = 'timeout'
    finally:
        # Always remove any surviving descendants, even after a normal parent exit.
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        proc.wait()
        sel.close()
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            stream.close()
    return {'returncode': proc.returncode, 'termination': reason,
            'seconds': time.monotonic()-started,
            **{name: bytes(value[:output_limit]).decode('utf-8', errors='replace') for name, value in buffers.items()}}
