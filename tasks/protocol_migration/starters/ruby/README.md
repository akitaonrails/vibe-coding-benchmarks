# Working v1 service

Run `sh build.sh` then `sh run.sh`; input and output are persistent JSONL.
Implement the accompanying CONTRACT.md v2 behavior while preserving v1 behavior.
Only src/** is editable. Build wrappers and dependency manifest/lock are protected.

- domain: stored-record conversion and wire views. A missing payload is distinct
  from a payload whose JSON value is null. Returns fresh view objects.
- repository: string-keyed storage and read cache. Reads return owned copies;
  writes invalidate that key's cached read, including previously cached misses.
- worker: mutates one owned record after checking transition preconditions;
  returns an error string or success. Generation counts each retry internally.
- solution: persistent repository owner and operation router.
- main: supplied line transport adapter.

V1 record data has id, state, generation, optional payload and optional reason.
States: pending/ready/failed/cancelled. Missing payload/reason means absent, not
null. The v1 wire projects these fields into id/status/optional value. A v2
implementation must introduce tenant scope throughout these boundaries.
