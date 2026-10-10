"""Descriptive aggregation only; no universal language ranking."""
from collections import Counter

def summarize(results):
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
