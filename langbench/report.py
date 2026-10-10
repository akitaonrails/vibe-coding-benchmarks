"""Descriptive aggregation only; no universal language ranking."""
from collections import Counter
from .metrics import reconcile_provider_usage

def summarize(results):
    if any(row.get('kind')=='development_smoke' for row in results):
        if not all(row.get('kind')=='development_smoke' for row in results):
            raise ValueError('cannot mix smoke attempts and flat grading results')
        return summarize_smokes(results)
    counts = Counter(row.get('validity', 'unknown') for row in results)
    valid = [row for row in results if row.get('validity') == 'valid']
    wins = sum(row.get('success') is True for row in valid)
    unresolved = len(results)-len(valid)
    denominator = len(results)
    return {'attempts':denominator, 'validity_counts':dict(counts), 'valid_successes':wins,
            'valid_attempt_success_rate':wins/len(valid) if valid else None,
            'operational_success_rate':wins/denominator if denominator else None,
            'missing_outcome_bounds':[wins/denominator,(wins+unresolved)/denominator] if denominator else None,
            'limitations':['Descriptive suite-conditional observations; no causal language ranking.',
                          'Reference self-tests are qualification evidence, not model outcomes.']}

def summarize_smokes(results):
    cells={}
    for row in results:
        treatment=row.get('manifest') or row.get('requested') or {}
        key=tuple(treatment.get(field,'unknown') for field in ('task','language','model','effort','tests'))
        cells.setdefault(key,[]).append(row)
    output=[]
    for key,rows in sorted(cells.items()):
        provider_analyses=[reconcile_provider_usage((row.get('collection') or row.get('partial_collection') or {}).get('invocations',[])) for row in rows]
        checkpoints=[]
        for index,label in enumerate(('unattended','nudge_1','nudge_2')):
            observed=[];reached=0;invalid_grades=0;statuses=Counter();seconds=0;tool_count=0;tool_seconds=0;provider_totals=[];partial_provider=0
            for row,provider in zip(rows,provider_analyses):
                turn_usage=next((turn for turn in provider['per_turn'] if turn['index']==index),None)
                if turn_usage is not None:
                    partial_provider+=turn_usage['known_subtotals']['totalTokens']
                    if turn_usage['complete']:provider_totals.append(turn_usage['provider_reported_total_tokens'])
                invocations=(row.get('collection') or row.get('partial_collection') or {}).get('invocations',[])
                invocation=next((item for item in invocations if item.get('index')==index),None)
                if invocation is not None:
                    reached+=1;statuses[invocation.get('status','unknown')]+=1
                    seconds+=invocation.get('seconds',0);tool_count+=invocation.get('tool_call_count',0);tool_seconds+=invocation.get('tool_seconds',0)
                grade=next((item for item in row.get('grades',[]) if item.get('index')==index),None)
                if grade is not None:
                    if grade.get('validity')=='valid' and invocation is not None and invocation.get('status') in ('handoff','timeout') and invocation.get('artifact_available'):
                        observed.append(grade.get('success') is True)
                    else:invalid_grades+=1
            checkpoints.append({'checkpoint':label,'reached':reached,'graded':len(observed),
                                'successes':sum(observed),'ungraded_or_invalid_reached':reached-len(observed),
                                'infrastructure_invalid_grades':invalid_grades,'status_counts':dict(statuses),
                                'incremental_active_seconds':seconds,'incremental_tool_calls':tool_count,'incremental_tool_seconds':tool_seconds,
                                'provider_reported_total_tokens':sum(provider_totals) if reached and len(provider_totals)==reached else None,
                                'complete_provider_usage_count':len(provider_totals),'observed_partial_provider_tokens':partial_provider,
                                'success_rate_among_graded':sum(observed)/len(observed) if observed else None})
        collections=[row.get('collection') or row.get('partial_collection') or {} for row in rows]
        invocations=[item for collection in collections for item in collection.get('invocations',[])]
        output.append({'treatment':dict(zip(('task','language','model','effort','tests'),key)),
            'requested_runs':len(rows),'launched_attempts':sum(bool(c.get('invocations')) for c in collections),
            'validity_counts':dict(Counter(row.get('validity','incomplete') for row in rows)),
            'checkpoints':checkpoints,'observed_active_seconds':sum(i.get('seconds',0) for i in invocations),
            'tool_calls':sum(i.get('tool_call_count',0) for i in invocations),
            'provider_reported_total_tokens':sum(analysis['provider_reported_total_tokens'] for analysis in provider_analyses) if provider_analyses and all(analysis['complete'] for analysis in provider_analyses) else None,
            'provider_usage_analysis':provider_analyses,'normalized_tokens':None,
            'token_accounting':'Explicit per-response provider counts reconciled with thread totals; broader benchmark qualification unchanged' })
    return {'kind':'development_smoke_report','cells':output,'limitations':[
        'Development smoke observations are not a powered language comparison.',
        'Unreached nudges and missing grades are shown separately, never imputed successes or failures.',
        'Provider counts are trace-reconciled consumption telemetry, not subscription billing or a normalized token efficiency ranking.']}
