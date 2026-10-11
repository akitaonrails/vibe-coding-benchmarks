#!/usr/bin/env python3
"""Preserve a stopped Claude cohort and create a no-retry instrumentation successor."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import shutil
import sys
sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from langbench.later_matrix import validate_plan
from langbench.matrix import input_binding
from langbench.subscriptions import sha
from scripts.analyze_subscription_matrix import validate_result

ADAPTER_SOURCES = ('claude_subscriptions.py','subscriptions.py','worker.py','mcp_bridge.py',
                   'provider_cli.py','provider_transport.py','provider_usage.py','assistance.py')


def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def inventory(root):
    result={}
    for path in sorted(root.rglob('*')):
        if path.is_symlink():raise ValueError('symlinks are not permitted in preserved cohort')
        if path.is_file():result[path.relative_to(root).as_posix()]=digest(path)
        elif not path.is_dir():raise ValueError('special file in cohort')
    return result


def qualification(data, frozen):
    if (data.get('passed') is not True or data.get('provider')!='claude' or
        data.get('model')!='claude-opus-5-5' or data.get('effort')!='medium'):
        raise ValueError('exact passed Claude medium qualification required')
    binding=data.get('binding')
    if not isinstance(binding,dict) or data.get('binding_sha256')!=sha(binding):
        raise ValueError('qualification binding hash mismatch')
    expected=sha({name:frozen['harness'][name] for name in ADAPTER_SOURCES})
    if binding.get('adapter_source_sha256')!=expected:
        raise ValueError('qualification does not match frozen adapter source')
    adapter=binding.get('adapter',{})
    if adapter.get('provider')!='claude' or adapter.get('model')!='claude-opus-5-5' or adapter.get('effort')!='medium':
        raise ValueError('qualified adapter identity mismatch')
    return binding


def allowed_change(before, after):
    expected=copy.deepcopy(before)
    expected['harness']['claude_subscriptions.py']=after['harness']['claude_subscriptions.py']
    if expected!=after or before==after:
        raise ValueError('only a changed claude_subscriptions.py binding is allowed')


def policy_change(old_binding, new_binding):
    comparable=copy.deepcopy(old_binding)
    comparable['adapter_source_sha256']=new_binding['adapter_source_sha256']
    old_policy=old_binding.get('adapter', {}).get('transport_policy')
    new_policy=new_binding.get('adapter', {}).get('transport_policy')
    if (old_policy,new_policy) in ((None,'serial-admission-v2'),('serial-admission-v2','serial-admission-v3')):
        comparable['adapter']['transport_policy']=new_policy
    if comparable!=new_binding:
        raise ValueError('qualification changed beyond allowed adapter source/policy')


def qualification_for_cell(directory, ident):
    directory=Path(directory)
    path=directory/'instrumentation-epoch.json'
    if path.exists():
        epoch=json.loads(path.read_bytes())
        if ident in epoch['consumed_ids']:
            return qualification_for_cell(directory/'lineage/predecessor', ident)
    return json.loads((directory/'qualification-claude.json').read_bytes())


def epoch_for_cell(directory, ident):
    q=qualification_for_cell(directory,ident)
    return q['binding']['adapter'].get('transport_policy') or 'original'


def fork(predecessor, destination, new_qualification, *, reason, current_binding=None):
    predecessor=Path(predecessor).resolve();destination=Path(destination).resolve()
    if destination.exists() or destination.is_relative_to(predecessor) or predecessor.is_relative_to(destination):
        raise ValueError('new separate destination required')
    if not isinstance(reason,str) or not reason.strip():raise ValueError('incident reason required')
    validate_lineage(predecessor)
    original=inventory(predecessor)
    state=json.loads((predecessor/'matrix.json').read_bytes());plan=json.loads((predecessor/'plan.json').read_bytes())
    cells=validate_plan(plan)
    if plan['provider']!='claude' or state.get('kind')!='later_subscription_matrix':raise ValueError('Claude follow-up only')
    if state.get('state')!='stopped_on_incident' or any(s.get('state')=='running' for s in state['cells']):
        raise ValueError('predecessor must be stopped with no running cells')
    if state.get('blocked_providers'):raise ValueError('quota-blocked cohort cannot be forked')
    if digest(predecessor/'plan.json')!=state['plan_sha256']:raise ValueError('plan commitment mismatch')
    if [s['id'] for s in state['cells']]!=[c['id'] for c in cells]:raise ValueError('cell identity mismatch')
    consumed=[];pending=[];seen_pending=False
    for cell,item in zip(cells,state['cells']):
        path=predecessor/cell['id']
        if item['state']=='pending':
            seen_pending=True;pending.append(cell['id'])
            if path.exists():raise ValueError('pending attempt directory exists')
            continue
        if seen_pending or item['state'] not in ('collected','infrastructure_invalid'):
            raise ValueError('consumed cells must be a closed prefix')
        if not item.get('result_sha256') or digest(path/'result.json')!=item['result_sha256']:
            raise ValueError('consumed result commitment mismatch')
        validate_result(cell,json.loads((path/'result.json').read_bytes()),path)
        consumed.append(cell['id'])
    if not consumed or not pending or state['cells'][len(consumed)-1]['state']!='infrastructure_invalid':
        raise ValueError('incident-ending consumed prefix and pending cells required')
    old_path=predecessor/'qualification-claude.json'
    if digest(old_path)!=state['qualification_sha256'].get('claude'):
        raise ValueError('old qualification commitment mismatch')
    before=state['input_binding'];after=current_binding if current_binding is not None else input_binding()
    allowed_change(before,after)
    old_q=json.loads(old_path.read_bytes());new_bytes=Path(new_qualification).read_bytes();new_q=json.loads(new_bytes)
    old_binding=qualification(old_q,before);new_binding=qualification(new_q,after)
    for ident in consumed:
        result=json.loads((predecessor/ident/'result.json').read_bytes())
        epoch_q=qualification_for_cell(predecessor,ident)
        if result.get('manifest') and (result['manifest'].get('binding')!=epoch_q['binding'] or result['manifest'].get('qualification_sha256')!=sha(epoch_q)):
            raise ValueError('consumed manifest qualification mismatch')
    policy_change(old_binding,new_binding)
    successor=copy.deepcopy(state);successor['input_binding']=after
    successor['qualification_sha256']={'claude':hashlib.sha256(new_bytes).hexdigest()}
    lineage={'schema_version':1,'kind':'claude_instrumentation_successor','reason':reason,
             'predecessor_path':str(predecessor),'plan_sha256':state['plan_sha256'],
             'predecessor_matrix_sha256':original['matrix.json'], 'before_binding':before,'after_binding':after,
             'old_qualification_sha256':digest(old_path),'new_qualification_sha256':hashlib.sha256(new_bytes).hexdigest(),
             'consumed_ids':consumed,'pending_ids':pending,'predecessor_inventory':original,
             'epochs':{'predecessor':consumed,'successor':pending},'archive_complete':True,
             'cell_epochs':{ident:epoch_for_cell(predecessor,ident) for ident in consumed}}
    lineage['cell_epochs'].update({ident:new_binding['adapter'].get('transport_policy') or 'original' for ident in pending})
    destination.mkdir(parents=True)
    try:
        archive=destination/'lineage/predecessor'
        archive.parent.mkdir(parents=True)
        shutil.copytree(predecessor,archive)
        for path in predecessor.iterdir():
            if path.is_file() and path.name not in ('matrix.json','qualification-claude.json'):
                shutil.copyfile(path,destination/path.name)
        for ident in consumed:shutil.copytree(predecessor/ident,destination/ident)
        (destination/'qualification-claude.json').write_bytes(new_bytes)
        (destination/'matrix.json').write_text(json.dumps(successor,indent=2)+'\n')
        (destination/'instrumentation-epoch.json').write_text(json.dumps(lineage,indent=2)+'\n')
        if inventory(predecessor)!=original:raise ValueError('predecessor changed during fork')
        for ident in consumed:
            if inventory(destination/ident)!=inventory(predecessor/ident):raise ValueError('preserved attempt copy mismatch')
        validate_lineage(destination)
    except Exception:
        # Preserve failed successor for diagnosis; never modify predecessor or retry it.
        (destination/'FORK_FAILED').write_text('Successor construction failed; do not resume.\n')
        raise
    return lineage


def validate_lineage(directory):
    directory=Path(directory);path=directory/'instrumentation-epoch.json'
    if not path.exists():return None
    if (directory/'FORK_FAILED').exists():raise ValueError('failed successor cannot be analyzed')
    epoch=json.loads(path.read_bytes());archive=directory/'lineage/predecessor'
    if epoch.get('schema_version')!=1 or epoch.get('kind')!='claude_instrumentation_successor':raise ValueError('unknown lineage schema')
    if digest(archive/'matrix.json')!=epoch['predecessor_matrix_sha256']:raise ValueError('archived predecessor mismatch')
    if digest(archive/'plan.json')!=epoch['plan_sha256'] or digest(directory/'plan.json')!=epoch['plan_sha256']:raise ValueError('lineage plan mismatch')
    if digest(archive/'qualification-claude.json')!=epoch['old_qualification_sha256'] or digest(directory/'qualification-claude.json')!=epoch['new_qualification_sha256']:raise ValueError('lineage qualification mismatch')
    if epoch.get('archive_complete') and inventory(archive)!=epoch['predecessor_inventory']:
        raise ValueError('archived predecessor inventory mismatch')
    validate_lineage(archive)
    old=json.loads((archive/'matrix.json').read_bytes());current=json.loads((directory/'matrix.json').read_bytes())
    allowed_change(epoch['before_binding'],epoch['after_binding'])
    if old['input_binding']!=epoch['before_binding'] or current['input_binding']!=epoch['after_binding']:raise ValueError('lineage source binding mismatch')
    old_q=json.loads((archive/'qualification-claude.json').read_bytes())
    new_q=json.loads((directory/'qualification-claude.json').read_bytes())
    old_binding=qualification(old_q,epoch['before_binding']);new_binding=qualification(new_q,epoch['after_binding'])
    policy_change(old_binding,new_binding)
    if old['qualification_sha256']!={'claude':epoch['old_qualification_sha256']} or current['qualification_sha256']!={'claude':epoch['new_qualification_sha256']}:raise ValueError('lineage state qualification mismatch')
    consumed=[s['id'] for s in old['cells'] if s['state']!='pending'];pending=[s['id'] for s in old['cells'] if s['state']=='pending']
    if consumed!=epoch['consumed_ids'] or pending!=epoch['pending_ids'] or epoch['epochs']!={'predecessor':consumed,'successor':pending}:raise ValueError('lineage epoch membership mismatch')
    current_cells={s['id']:s for s in current['cells']}
    for item in old['cells']:
        if item['id'] in consumed:
            if current_cells.get(item['id'])!=item:raise ValueError('consumed attempt was changed or retried')
            if digest(directory/item['id']/'result.json')!=item['result_sha256']:raise ValueError('consumed receipt changed')
    if 'cell_epochs' in epoch:
        expected={ident:epoch_for_cell(archive,ident) for ident in consumed}
        expected.update({ident:new_binding['adapter'].get('transport_policy') or 'original' for ident in pending})
        if epoch['cell_epochs']!=expected:raise ValueError('nested epoch attribution mismatch')
    return epoch


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('predecessor',type=Path);parser.add_argument('destination',type=Path)
    parser.add_argument('--qualification',required=True,type=Path);parser.add_argument('--reason',required=True)
    args=parser.parse_args();fork(args.predecessor,args.destination,args.qualification,reason=args.reason)

if __name__=='__main__':main()
