"""Conservative CLI-normalized usage; native missing fields are never inferred."""
import json

VERSION='subscription-usage-v1'


def record(provider, identity, raw):
    if provider=='kimi':
        fields={'input':'inputOther','cache_read':'inputCacheRead','cache_write':'inputCacheCreation','output':'output'}
        values={key:raw.get(field) for key,field in fields.items()}
        values['reasoning']=None
        mapping='disjoint input/cache/output; cache creation assigned zero by CLI; reasoning unavailable'
    elif provider=='opencode':
        values={key:raw.get(key) for key in ('input','output','reasoning')}
        cache=raw.get('cache') if isinstance(raw.get('cache'),dict) else {}
        values.update(cache_read=cache.get('read'),cache_write=cache.get('write'))
        mapping='CLI subtracts cache from input and reasoning from output; components disjoint'
    else:raise ValueError('unsupported provider')
    valid=all(value is None or type(value) is int and value>=0 for value in values.values())
    required=('input','cache_read','cache_write','output') if provider=='kimi' else tuple(values)
    total=sum(values[key] for key in required) if valid and all(values[key] is not None for key in required) else None
    return {'parser_version':VERSION,'provider':provider,'request_id':identity,'raw':raw,
            'components':values,'cli_normalized_total':total,'scope':'request',
            'native_fields_verified':False,'mapping':mapping,'valid':valid}


def summarize(records):
    seen={};conflicts=[]
    for item in records:
        key=(item['provider'],item['request_id'])
        if key in seen and seen[key]!=item:conflicts.append(str(key))
        seen[key]=item
    observed_complete=bool(seen) and not conflicts and all(item['cli_normalized_total'] is not None for item in seen.values())
    complete=observed_complete and all(item.get('request_coverage_verified') is True for item in seen.values())
    native_complete=bool(seen) and not conflicts and all(item.get('native_fields_verified') is True and item.get('provider_reported_total') is not None for item in seen.values())
    known_native=[item['provider_reported_total'] for item in seen.values() if item.get('native_fields_verified') is True and item.get('provider_reported_total') is not None]
    return {'provider_reported_known_subtotal':sum(known_native) if known_native else None,
            'provider_reported_total':sum(item['provider_reported_total'] for item in seen.values()) if native_complete else None,
            'native_request_coverage_complete':native_complete,'parser_version':VERSION,'request_count':len(seen),'duplicate_conflicts':conflicts,
            'cli_normalized_total':sum(item['cli_normalized_total'] for item in seen.values()) if complete else None,
            'observed_records_subtotal':sum(item['cli_normalized_total'] for item in seen.values()) if observed_complete else None,
            'completeness':'transport_reconciled' if complete else 'unknown_or_conflicting',
            'native_fields_verified':False,'billing_total':None,
            'scope_limit':'Completeness concerns observed records; transport/export completeness must be established separately.'}


def native_record(provider,request):
    """Native Chat Completions totals; cache/reasoning are subsets, not addends."""
    usage=request.get('usage',[])
    raw=usage[-1] if usage else {}
    input_tokens=raw.get('prompt_tokens');output_tokens=raw.get('completion_tokens');total=raw.get('total_tokens')
    valid=all(type(v) is int and v>=0 for v in (input_tokens,output_tokens,total)) and total==input_tokens+output_tokens
    cached=(raw.get('prompt_tokens_details') or {}).get('cached_tokens')
    reasoning=(raw.get('completion_tokens_details') or {}).get('reasoning_tokens')
    if cached is not None:valid=valid and type(cached) is int and 0<=cached<=input_tokens
    if reasoning is not None:valid=valid and type(reasoning) is int and 0<=reasoning<=output_tokens
    complete=valid and request.get('response_complete') is True and request.get('http_status')==200
    return {'parser_version':VERSION,'provider':provider,'request_id':'transport-'+str(request['index']),
            'raw':raw,'scope':'request','components':{'input_including_cache':input_tokens,'output_including_reasoning':output_tokens,'cache_read':cached,'cache_write':None,'reasoning':reasoning},
            'cli_normalized_total':None,'provider_reported_total':total if complete else None,
            'native_fields_verified':complete,'request_coverage_verified':complete,
            'mapping':'Provider input/output inclusive; cache and reasoning reported as subsets; no separate write-cache inference.',
            'valid':valid}


def summarize_invocations(invocations):
    summary=summarize([record for invocation in invocations for record in invocation.get('usage_records',[])])
    covered=bool(invocations) and all(invocation.get('usage_coverage_verified') is True for invocation in invocations)
    summary['all_invocations_covered']=covered
    if not covered:
        summary['provider_reported_partial_subtotal']=summary['provider_reported_total']
        summary['provider_reported_total']=None
        summary['cli_normalized_total']=None
        summary['native_request_coverage_complete']=False
    return summary
