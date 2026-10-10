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
