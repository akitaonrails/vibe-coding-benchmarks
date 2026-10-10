"""Public examples only; run with python3 test_public.py after ./build.sh."""
import json
from pathlib import Path
import subprocess

def same_json(actual, expected):
    # Contracts use integral numbers; booleans must never match 0/1.
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(same_json(actual[key], value) for key, value in expected.items())
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(same_json(a, b) for a, b in zip(actual, expected))
    return actual == expected

if __name__ == '__main__':
    for case in json.loads(Path('public_cases.json').read_text()):
        run = subprocess.run(['./run.sh'], input=''.join(json.dumps(r)+'\n' for r in case['requests']), text=True, capture_output=True, timeout=10)
        actual = [json.loads(line) for line in run.stdout.splitlines()]
        assert run.returncode == 0 and same_json(actual, case['expected']), case['id']
    print('Public cases passed')
