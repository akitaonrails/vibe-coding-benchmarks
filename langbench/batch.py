"""Sequential development-plan executor with a durable, stop-on-incident ledger."""
import hashlib
import json
import os
from pathlib import Path
from .appserver import DEFAULT_BINARY
from .core import TASKS, IMPLEMENTED

PLAN_FIELDS={'schema_version','seed','scored_execution_qualified','cells'}
CELL_FIELDS={'task','language','tests','model','effort','replicate','block_id','semantic_seed',
             'base_seconds','continuation_seconds','max_nudges','auth_mode'}
MODELS={'gpt-6-astra','gpt-6-sol','gpt-6-luna'}

def validate_plan(plan,limit=None):
    if not isinstance(plan,dict) or set(plan)-{'purpose'}!=PLAN_FIELDS:raise ValueError('unknown or missing plan fields')
    if type(plan['schema_version']) is not int or plan['schema_version']!=1:raise ValueError('unsupported plan schema')
    if type(plan['seed']) is not int or plan['seed']<0:raise ValueError('invalid randomization seed')
    if plan['scored_execution_qualified'] is not False:raise ValueError('batch supports unqualified development smoke plans only')
    if not isinstance(plan['cells'],list) or not plan['cells']:raise ValueError('plan requires cells')
    if limit is not None and (type(limit) is not int or limit<=0):raise ValueError('limit must be positive')
    purpose=plan.get('purpose','smoke')
    if purpose not in ('smoke','calibration'):raise ValueError('invalid plan purpose')
    selected=plan['cells'][:limit]
    for cell in selected:
        if not isinstance(cell,dict) or set(cell)!=CELL_FIELDS:raise ValueError('unknown or missing cell fields')
        for field,allowed in (('task',TASKS),('language',IMPLEMENTED),('tests',('T0','T1')),
                              ('model',MODELS),('effort',('low','medium','high'))):
            if not isinstance(cell[field],str) or cell[field] not in allowed:raise ValueError('invalid cell '+field)
        for field in ('replicate','base_seconds','continuation_seconds'):
            if type(cell[field]) is not int or cell[field]<=0:raise ValueError('invalid cell '+field)
        if type(cell['semantic_seed']) is not int or cell['semantic_seed']<0:raise ValueError('invalid semantic seed')
        if type(cell['max_nudges']) is not int or cell['max_nudges']!=2:raise ValueError('main policy requires two nudges')
        if purpose=='calibration' and cell['task'] in ('crash_store','protocol_migration'):
            raise ValueError('smoke controls cannot be presented as calibration tasks')
        if cell['auth_mode']!='chatgpt':raise ValueError('subscription auth required')
        if not isinstance(cell['block_id'],str) or not cell['block_id'] or any(c in cell['block_id'] for c in '\r\n\0'):
            raise ValueError('invalid block ID')
    return selected

def batch(plan_file,destination,*,limit=None,binary=DEFAULT_BINARY,runner=None):
    source=Path(plan_file)
    if source.stat().st_size>1024*1024:raise ValueError('plan exceeds 1 MiB')
    raw=source.read_bytes();plan=json.loads(raw);selected=validate_plan(plan,limit)
    output=Path(destination).absolute();output.mkdir(parents=True,exist_ok=False)
    with (output/'plan.json').open('xb') as handle:
        handle.write(raw);handle.flush();os.fsync(handle.fileno())
    summary={'kind':'development_batch','schema_version':1,'scored_execution_qualified':False,
             'plan_sha256':hashlib.sha256(raw).hexdigest(),'total_plan_cells':len(plan['cells']),
             'requested_limit':limit,'selected_count':len(selected),'execution':'sequential','state':'running','attempts':[]}
    def persist(event=None):
        if event is not None:
            with (output/'progress.jsonl').open('a') as handle:
                handle.write(json.dumps(event,sort_keys=True)+'\n');handle.flush();os.fsync(handle.fileno())
        temporary=output/'batch.json.tmp'
        with temporary.open('w') as handle:
            json.dump(summary,handle,indent=2);handle.write('\n');handle.flush();os.fsync(handle.fileno())
        temporary.replace(output/'batch.json')
    persist({'event':'frozen','plan_sha256':summary['plan_sha256'],'selected_count':len(selected)})
    if runner is None:
        from .live import run
        runner=run
    for index,cell in enumerate(selected):
        name=f"{index+1:04d}-{cell['task']}-{cell['language']}-{cell['tests']}"
        attempt=output/name
        persist({'event':'started','index':index,'path':name,'cell':cell})
        try:
            result=runner(cell['task'],cell['language'],attempt,tests=cell['tests'],model=cell['model'],effort=cell['effort'],
                          base_seconds=cell['base_seconds'],continuation_seconds=cell['continuation_seconds'],
                          seed=cell['semantic_seed'],replicate=cell['replicate'],block_id=cell['block_id'],binary=binary)
            if not isinstance(result,dict):raise ValueError('runner returned invalid result')
        except KeyboardInterrupt:
            summary['state']='interrupted'
            record={'index':index,'path':name,'validity':'interrupted','result_path':name+'/result.json'}
            summary['attempts'].append(record);persist({'event':'interrupted',**record})
            return summary
        except Exception as exc:
            result={'kind':'development_smoke','validity':'infrastructure_invalid','error':type(exc).__name__+': '+str(exc)[:300]}
        attempt.mkdir(exist_ok=True)
        result_path=attempt/'result.json'
        if not result_path.exists():
            with result_path.open('x') as handle:json.dump(result,handle,indent=2);handle.write('\n')
        collection=result.get('collection') or result.get('partial_collection') or {}
        quota=any(item.get('status')=='quota' for item in collection.get('invocations',[]))
        record={'index':index,'path':name,'result_path':name+'/result.json','validity':result.get('validity','unknown'),
                'quota':quota,'result_sha256':hashlib.sha256(result_path.read_bytes()).hexdigest()}
        summary['attempts'].append(record)
        if record['validity']!='valid_smoke' or quota:
            summary['state']='stopped_on_incident';persist({'event':'completed',**record});return summary
        persist({'event':'completed',**record})
    summary['state']='complete';persist({'event':'complete','attempt_count':len(summary['attempts'])})
    return summary
