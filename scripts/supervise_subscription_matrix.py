#!/usr/bin/env python3
"""Resume only two diagnosed operational incidents; never repair or retry a cell."""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

MAX_JSON=32*1024*1024


def read_json(path):
    path=Path(path)
    if path.stat().st_size>MAX_JSON:raise RuntimeError('receipt exceeds inspection bound')
    return json.loads(path.read_bytes())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def append(path,event):
    with Path(path).open('a') as handle:
        handle.write(json.dumps({'time':time.time(),**event},sort_keys=True)+'\n')
        handle.flush();os.fsync(handle.fileno())


def matrix_argv(argv,cwd,destination):
    """Match executable argument tokens, never a shell's quoted command string."""
    try:index=argv.index('-m')
    except ValueError:return False
    if argv[index+1:index+3]!=['langbench','matrix-run'] or len(argv)<=index+4:return False
    return (Path(cwd)/argv[index+4]).resolve()==Path(destination).resolve()


def processes(destination,proc_root=Path('/proc')):
    matrices=[];orphans=[]
    for entry in proc_root.iterdir():
        if not entry.name.isdigit() or int(entry.name)==os.getpid():continue
        try:
            argv=[part.decode(errors='replace') for part in (entry/'cmdline').read_bytes().split(b'\0') if part]
            if not argv:continue
            cwd=(entry/'cwd').resolve()
            if matrix_argv(argv,cwd,destination):matrices.append(int(entry.name));continue
            # Read only the relevant environment keys; no values leave this function.
            environment=dict(part.split(b'=',1) for part in (entry/'environ').read_bytes().split(b'\0') if b'=' in part)
            isolated=any(environment.get(key,b'').startswith(b'/tmp/langbench-provider-') for key in (b'HOME',b'KIMI_CODE_HOME'))
            mcp=any(Path(arg).name=='mcp_bridge.py' for arg in argv) and '--socket' in argv
            if isolated or mcp:orphans.append(int(entry.name))
        except (OSError,ValueError):continue # process disappeared or belongs to another user
    return matrices,orphans


def no_orphans(destination):
    matrices,orphans=processes(destination)
    if matrices or orphans:return False,{'matrix_processes':len(matrices),'provider_processes':len(orphans)}
    check=subprocess.run(['docker','ps','-a','--filter','name=langbench-','--format','{{.Names}}'],capture_output=True,text=True,timeout=10)
    if check.returncode:return False,{'docker_inspection_failed':True}
    names=[line for line in check.stdout.splitlines() if line.startswith('langbench-')]
    return not names,{'matrix_processes':0,'provider_processes':0,'benchmark_containers':len(names)}


def classify(result,raw):
    """Exact allowlist: unknown errors must stop for inspection."""
    if result.get('validity')!='infrastructure_invalid' or result.get('phase')!='complete' or result.get('error'):
        return None
    invocations=(result.get('collection') or {}).get('invocations',[])
    if len(invocations)!=1:return None
    invocation=invocations[0]
    boundaries=invocation.get('boundary_error',{})
    if boundaries!={'bridge':None,'transport':None}:return None
    if invocation.get('quiescent') is True and invocation.get('artifact_available') is True:
        if result.get('requested',{}).get('provider')!='opencode':return None
        if invocation.get('status')!='infrastructure_error' or invocation.get('error')!='CLI failed or missing terminal event':return None
        if raw.get('returncode')!=0 or raw.get('termination') is not None or raw.get('stderr',''):return None
        events=[]
        for line in raw.get('stdout','').splitlines():
            if line.strip():
                try:events.append(json.loads(line))
                except ValueError:return None
        if events!=invocation.get('events'):return None
        if any(event.get('type')=='error' for event in events):return None
        if not events or events[-1].get('type')!='step_finish' or events[-1].get('part',{}).get('reason')!='length':return None
        return 'model_output_limit'
    cleanup=invocation.get('cleanup_unsettled')
    if (invocation.get('status')=='timeout' and invocation.get('quiescent') is False
        and invocation.get('artifact_available') is False and invocation.get('error') is None
        and cleanup==[{'component':'transport','error_type':'RuntimeError'}]
        and raw.get('termination')=='timeout' and raw.get('returncode')==-9
        and all(tool.get('state')=='finished' for tool in invocation.get('tool_records',[]))):
        return 'timeout_transport_drain_preserved_invalid'
    return None


def diagnosed_incident(destination,state):
    consumed=[cell for cell in state['cells'] if cell['state']!='pending']
    if not consumed or consumed[-1]['state']!='infrastructure_invalid':raise RuntimeError('unknown stop state')
    cell=consumed[-1]
    if not isinstance(cell['id'],str) or Path(cell['id']).name!=cell['id']:raise RuntimeError('invalid cell identity')
    directory=destination/cell['id'];path=directory/'result.json'
    if digest(path)!=cell.get('result_sha256'):raise RuntimeError('result commitment mismatch')
    result=read_json(path);raw_path=directory/'trace/invocation-0.json';raw=read_json(raw_path)
    signature=classify(result,raw)
    if signature is None:raise RuntimeError('unknown incident signature')
    return cell,signature,digest(raw_path)


def supervise(destination,plan,qualifications,*,poll_seconds=10,process_scan=processes,orphan_check=no_orphans,run=subprocess.run,sleep=time.sleep):
    destination=Path(destination).resolve()
    audit=destination/'supervisor-audit.jsonl'
    seen=set();iteration=0
    if audit.exists():
        if audit.stat().st_size>MAX_JSON:raise RuntimeError('audit exceeds inspection bound')
        for line in audit.read_text().splitlines():
            event=json.loads(line)
            if event.get('event')=='incident_resume_authorized':
                seen.add((event['cell'],event['raw_result_sha256']))
    while True:
        active,_=process_scan(destination)
        if active:
            if len(active)!=1:raise RuntimeError('multiple matrix controllers detected')
            append(audit,{'event':'waiting_existing_matrix','process_count':1})
            while True:
                active,_=process_scan(destination)
                if not active:break
                if len(active)!=1:raise RuntimeError('multiple matrix controllers detected during attach')
                sleep(poll_seconds)
        state=read_json(destination/'matrix.json')
        if state['state'] in ('complete','closed_with_missing_cells'):
            if any(cell['state'] in ('pending','running') for cell in state['cells']):raise RuntimeError('closed campaign retains unfinished cells')
            append(audit,{'event':'campaign_closed','state':state['state'],'pending':sum(c['state']=='pending' for c in state['cells'])})
            return state['state']
        if state['state']!='stopped_on_incident':raise RuntimeError('controller exited without a diagnosed incident')
        cell,signature,raw_hash=diagnosed_incident(destination,state)
        identity=(cell['id'],cell['result_sha256'])
        if identity in seen:raise RuntimeError('resume made no progress; refusing repeated restart')
        clean,evidence=orphan_check(destination)
        if not clean:raise RuntimeError('benchmark cleanup not verified')
        seen.add(identity)
        action={'actor':'AI-authored operational supervisor','cell':cell['id'],'raw_result_sha256':cell['result_sha256'],
                'raw_process_sha256':raw_hash,'signature':signature,'candidate_repairs':0,'additional_nudges':0,
                'human_labor_seconds':None,'cleanup_evidence':evidence,
                'action':'Resume pending cells unchanged; consumed cell is never retried.'}
        if signature=='model_output_limit':
            append(destination/'outcome-overrides.jsonl',{'schema_version':1,**action,'analysis_classification':'model_output_limit','raw_classification':'infrastructure_invalid'})
        append(audit,{'event':'incident_resume_authorized',**action})
        # Existing runner independently checks frozen plan/qualifications/code/results.
        command=[sys.executable,'-m','langbench','matrix-run',str(Path(plan).resolve()),str(destination),
                 '--kimi-qualification',str(Path(qualifications['kimi']).resolve()),
                 '--opencode-qualification',str(Path(qualifications['opencode']).resolve()),'--resume']
        iteration+=1
        log=destination/f'supervisor-resume-{time.time_ns()}-{iteration}.log'
        with log.open('x') as handle:
            completed=run(command,stdout=handle,stderr=subprocess.STDOUT,check=False)
        append(audit,{'event':'resume_process_exited','returncode':completed.returncode,'log':log.name})
        print(json.dumps({'event':'resume_process_exited','returncode':completed.returncode,'incident_cell':cell['id']}),flush=True)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('destination',type=Path);parser.add_argument('--plan',type=Path,required=True)
    parser.add_argument('--kimi-qualification',type=Path,required=True);parser.add_argument('--opencode-qualification',type=Path,required=True)
    args=parser.parse_args();destination=args.destination.resolve()
    with (destination/'supervisor.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        try:
            status=supervise(destination,args.plan,{'kimi':args.kimi_qualification,'opencode':args.opencode_qualification})
            print(json.dumps({'state':status}));return 0
        except Exception as error:
            # Deliberately omit exception text and command output from the console.
            append(destination/'supervisor-audit.jsonl',{'event':'failed_closed','error_type':type(error).__name__})
            print(json.dumps({'state':'failed_closed','error_type':type(error).__name__}));return 1


if __name__=='__main__':raise SystemExit(main())
