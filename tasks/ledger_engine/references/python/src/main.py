"""Persistent JSONL transport; domain code performs all operations."""
import json
import sys
from solution import Engine

engine = Engine()
for line in sys.stdin:
    print(json.dumps(engine.handle(json.loads(line))), flush=True)
