"""Never interpret unknown usage semantics as measured totals."""
from dataclasses import dataclass

@dataclass(frozen=True)
class UsageSemantics:
    scope: str = 'unknown'  # per_turn or cumulative_thread after qualification
    reasoning: str = 'unknown'  # included or disjoint
    cached_subset: bool = False
    qualified: bool = False

    def __post_init__(self):
        if self.scope not in ('unknown', 'per_turn', 'cumulative_thread') or self.reasoning not in ('unknown', 'included', 'disjoint'):
            raise ValueError('invalid usage semantics')

def normalize_usage(events, semantics=UsageSemantics()):
    fields = ('input_tokens', 'cached_input_tokens', 'output_tokens', 'reasoning_output_tokens')
    totals = dict.fromkeys(fields, 0)
    complete = dict.fromkeys(fields, True)
    seen = {}
    previous = {}
    warnings = []
    turns = 0
    active_turn = False
    for event in events:
        if event.get('type') == 'turn.started':
            active_turn = True
        elif event.get('type') in ('turn.failed', 'error'):
            warnings.append('failed_or_incomplete_turn')
        elif event.get('type') == 'turn.completed':
            active_turn = False
        if event.get('type') != 'turn.completed':
            continue
        usage = event.get('usage')
        key = event.get('turn_id') or event.get('id')
        if key is None:
            warnings.append('missing_stable_turn_id')
        else:
            if key in seen:
                if seen[key] != usage:
                    warnings.append('conflicting_duplicate_turn')
                continue
            seen[key] = usage
        turns += 1
        if not isinstance(usage, dict):
            warnings.append('missing_usage')
            usage = {}
        for field in fields:
            value = usage.get(field)
            if type(value) is not int or value < 0:
                complete[field] = False
                continue
            if semantics.scope == 'cumulative_thread':
                # Input must belong to one complete thread, starting at its origin.
                increment = value - previous.get(field, 0)
                if increment < 0:
                    warnings.append('nonmonotonic_cumulative_usage')
                    complete[field] = False
                    continue
                previous[field] = value
            else:
                increment = value
            totals[field] += increment
    if active_turn:
        warnings.append('unfinished_turn')
    if not turns:
        warnings.append('no_completed_turns')
    if not semantics.qualified or semantics.scope == 'unknown':
        warnings.append('usage_scope_unqualified')
    if semantics.reasoning == 'unknown':
        warnings.append('reasoning_overlap_unqualified')
    measured = {field: totals[field] if complete[field] and turns else None for field in fields}
    total = None
    if not warnings and measured['input_tokens'] is not None and measured['output_tokens'] is not None:
        total = measured['input_tokens'] + measured['output_tokens']
        if semantics.reasoning == 'disjoint':
            total = total + measured['reasoning_output_tokens'] if measured['reasoning_output_tokens'] is not None else None
    uncached = None
    if semantics.cached_subset and measured['input_tokens'] is not None and measured['cached_input_tokens'] is not None:
        uncached = measured['input_tokens'] - measured['cached_input_tokens']
        if uncached < 0:
            warnings.append('cached_exceeds_input')
            uncached = None
            total = None
    return {'parser_version':1, 'raw_components':measured, 'total_tokens':total, 'uncached_input_tokens':uncached,
            'unique_completed_turns':turns, 'warnings':sorted(set(warnings)), 'complete':total is not None}

PROVIDER_FIELDS = ('totalTokens','inputTokens','cachedInputTokens','cacheWriteInputTokens','outputTokens','reasoningOutputTokens')

def reconcile_provider_usage(invocations):
    """Reconcile explicit per-response provider totals against one fresh thread.

No inference about billing, invisible compute, or other CLI versions is made.
Request-level `last` counters are deliberately never summed as user-turn usage.
"""
    issues=set();turns={};order=[];responses={};thread_ids=set();updates={}
    for index, invocation in enumerate(invocations):
        turn=invocation.get('turn_id')
        if not isinstance(turn,str) or not turn or turn in turns:
            issues.add('missing_or_duplicate_turn_id')
            continue
        order.append(turn)
        turns[turn]={'index':invocation.get('index',index),'status':invocation.get('status'),
                     'response_ids':[],'issues':set(),'known_subtotals':dict.fromkeys(PROVIDER_FIELDS,0),
                     'field_complete':dict.fromkeys(PROVIDER_FIELDS,True)}
        if invocation.get('status')!='handoff':turns[turn]['issues'].add('incomplete_turn')
    for invocation in invocations:
        for event in invocation.get('events',[]):
            method=event.get('method');params=event.get('params',{})
            if method not in ('rawResponse/completed','thread/tokenUsage/updated'):continue
            turn=params.get('turnId');thread=params.get('threadId')
            if not isinstance(thread,str) or not thread:issues.add('missing_thread_id')
            else:thread_ids.add(thread)
            if turn not in turns:
                issues.add('unknown_usage_turn');continue
            if method=='thread/tokenUsage/updated':
                total=(params.get('tokenUsage') or {}).get('total')
                updates.setdefault(turn,[]).append(total)
                continue
            response=params.get('responseId');usage=params.get('usage')
            metadata=params.get('usageMetadata') or {}
            if not isinstance(response,str) or not response:
                turns[turn]['issues'].add('missing_response_id');continue
            native=metadata.get('metadata') if isinstance(metadata,dict) else None
            native_details=native.get('output_tokens_details') if isinstance(native,dict) else None
            reasoning_identity=(isinstance(native_details,dict) and 'reasoning_tokens' in native_details,
                                native_details.get('reasoning_tokens') if isinstance(native_details,dict) else None)
            identity={'turn':turn,'thread':thread,'usage':usage,'native_reasoning':reasoning_identity}
            if response in responses:
                if responses[response]!=identity:
                    issues.add('conflicting_duplicate_response')
                    turns[turn]['issues'].add('conflicting_duplicate_response')
                continue
            responses[response]=identity
            turns[turn]['response_ids'].append(response)
            if not isinstance(usage,dict):usage={}
            valid={field: type(usage.get(field)) is int and usage[field]>=0 for field in PROVIDER_FIELDS}
            for field in PROVIDER_FIELDS:
                if valid[field]:turns[turn]['known_subtotals'][field]+=usage[field]
                else:
                    turns[turn]['field_complete'][field]=False
                    turns[turn]['issues'].add('missing_or_invalid_'+field)
            if all(valid[field] for field in ('totalTokens','inputTokens','outputTokens')) and usage['totalTokens']!=usage['inputTokens']+usage['outputTokens']:
                turns[turn]['issues'].add('provider_total_component_mismatch')
            for subset,total in (('cachedInputTokens','inputTokens'),('cacheWriteInputTokens','inputTokens'),('reasoningOutputTokens','outputTokens')):
                if valid[subset] and valid[total] and usage[subset]>usage[total]:
                    turns[turn]['issues'].add('invalid_subset_'+subset)
            native=metadata.get('metadata') if isinstance(metadata,dict) else None
            if isinstance(native,dict):
                details=native.get('output_tokens_details')
                if isinstance(details,dict) and 'reasoning_tokens' in details:
                    reasoning=details['reasoning_tokens']
                    if type(reasoning) is not int or reasoning<0 or not valid['reasoningOutputTokens'] or reasoning!=usage['reasoningOutputTokens']:
                        turns[turn]['issues'].add('native_reasoning_metadata_mismatch')
    if len(thread_ids)!=1:issues.add('expected_one_fresh_thread')
    if not responses:issues.add('no_response_usage')
    cumulative=dict.fromkeys(PROVIDER_FIELDS,0);cumulative_complete=dict.fromkeys(PROVIDER_FIELDS,True)
    per_turn=[]
    for turn in order:
        entry=turns[turn]
        if not entry['response_ids']:entry['issues'].add('no_response_usage_for_turn')
        for field in PROVIDER_FIELDS:
            cumulative[field]+=entry['known_subtotals'][field]
            cumulative_complete[field] &= entry['field_complete'][field]
        history=updates.get(turn,[]);last=history[-1] if history else None
        if not isinstance(last,dict):
            entry['issues'].add('missing_thread_cumulative_usage')
            reconciled=False
        else:
            reconciled=True
            previous=None
            for update in history:
                if not isinstance(update,dict):entry['issues'].add('invalid_thread_cumulative_usage');continue
                for field in PROVIDER_FIELDS:
                    value=update.get(field)
                    if type(value) is not int or value<0:entry['issues'].add('invalid_cumulative_'+field)
                    elif previous is not None and type(previous.get(field)) is int and value<previous[field]:
                        entry['issues'].add('nonmonotonic_thread_cumulative')
                previous=update
            for field in PROVIDER_FIELDS:
                value=last.get(field)
                if type(value) is not int or not cumulative_complete[field] or value!=cumulative[field]:
                    reconciled=False
                    entry['issues'].add('cumulative_mismatch_'+field)
        complete=not entry['issues'] and not issues and reconciled
        per_turn.append({'turn_id':turn,'index':entry['index'],'response_count':len(entry['response_ids']),
                         'provider_reported_total_tokens':entry['known_subtotals']['totalTokens'] if complete else None,
                         'observed_components':{field:entry['known_subtotals'][field] if entry['field_complete'][field] else None for field in PROVIDER_FIELDS},
                         'known_subtotals':entry['known_subtotals'],'cumulative_reconciled':reconciled,
                         'complete':complete,'warnings':sorted(entry['issues'])})
    complete=bool(per_turn) and not issues and all(row['complete'] for row in per_turn)
    return {'parser_version':'appserver-response-v1','response_count':len(responses),
            'provider_reported_total_tokens':cumulative['totalTokens'] if complete else None,
            'observed_components':{field:cumulative[field] if cumulative_complete[field] else None for field in PROVIDER_FIELDS},
            'known_subtotals':cumulative,'complete':complete,'per_turn':per_turn,'warnings':sorted(issues),
            'scope':'Explicit provider per-response counts, deduplicated and reconciled with fresh-thread cumulative counters.',
            'limitations':['Pinned trace observations; not subscription billing or invisible reasoning compute.',
                           'Reasoning and cached input are reported subsets and are never added to totalTokens.',
                           'Incomplete turns retain partial observations without claiming complete effort.']}
