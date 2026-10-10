"""Fail-closed difficulty calibration; source size is never an eligibility input."""
from collections import Counter, defaultdict
from .core import task_path
import json

def calibrate(results,metadata=None):
    valid=[];excluded=Counter();roles=set();instances=defaultdict(lambda:defaultdict(set));metadata=metadata or {};seen=set()
    for row in results:
        manifest=row.get('manifest') or {};task=manifest.get('task')
        attempt=manifest.get('attempt_id')
        if not isinstance(attempt,str) or not attempt or attempt in seen:
            excluded['missing_or_duplicate_attempt_identity']+=1;continue
        seen.add(attempt)
        if task not in metadata:
            try:metadata[task]=json.loads((task_path(task)/'task.json').read_text())
            except (ValueError,OSError,TypeError):metadata[task]={}
        difficulty=metadata[task].get('difficulty',{});roles.add(difficulty.get('role','unclassified'))
        invocation=next((i for i in (row.get('collection') or {}).get('invocations',[]) if i.get('index')==0),None)
        grade=next((g for g in row.get('grades',[]) if g.get('index')==0),None)
        if invocation is None or invocation.get('status')=='timeout':excluded['missing_or_censored']+=1;continue
        if invocation.get('status')!='handoff' or not invocation.get('artifact_available') or grade is None or grade.get('validity')!='valid':
            excluded['infrastructure_or_ungraded']+=1;continue
        valid.append((manifest,grade.get('success') is True,difficulty))
        instance=difficulty.get('independent_instance_id')
        if difficulty.get('independence_reviewed') is True and instance:
            instances[instance][manifest.get('language')].add(manifest.get('replicate'))
    wins=sum(passed for _,passed,_ in valid);reasons=[]
    if not valid:reasons.append('no_valid_initial_outcomes')
    if len(valid)>=4 and wins==len(valid):reasons.append('observed_first_handoff_ceiling')
    if excluded:reasons.append('censored_or_invalid_attempts_require_separate_resolution')
    if roles!={'calibration_candidate'}:reasons.append('contains_smoke_or_unclassified_tasks')
    if len(instances)<3 or any(any(len(languages.get(language,set())-{None})<2 for language in ('ruby','rust')) for languages in instances.values()):
        reasons.append('need_at_least_three_reviewed_independent_instances_with_two_replicates_each')
    strong=[passed for manifest,passed,_ in valid if manifest.get('model')=='gpt-6-astra' and manifest.get('base_seconds',0)>=900]
    if len(strong)<12 or not (any(strong) and not all(strong)):
        reasons.append('need_prespecified_strong_model_budget_and_mixed_pooled_outcomes')
    if len({(m.get('model'),m.get('effort'),m.get('base_seconds'),m.get('tests')) for m,_,_ in valid})>1:
        reasons.append('analyze_separate_prespecified_model_budget_test_cohorts')
    eligible=not reasons
    return {'schema_version':1,'valid_initial_outcomes':len(valid),'initial_successes':wins,
            'first_handoff_ceiling_observed':len(valid)>=4 and wins==len(valid),'excluded':dict(excluded),
            'reviewed_independent_instances':len(instances),'difficulty_gate_passed':eligible,
            'frontier_eligible':eligible,'comparison_eligible':eligible and all(row.get('scored_benchmark_qualified') is True for row in results),
            'reasons':reasons,'policy':{'minimum_independent_instances':3,'minimum_replicates_per_instance':2,'minimum_pooled_strong_observations':12,
                'minimum_initial_seconds':900,'size_threshold':None,'equal_language_success_rates_required':False},
            'limitations':['Necessary development-screening gate, not a power calculation or proof of frontier difficulty.',
                           'Generated seeds of one workload do not establish independent semantic instances.',
                           'Difficulty selection pools languages and never requires similar Ruby/Rust success rates.']}
