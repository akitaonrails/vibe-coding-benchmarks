# Published measurements

[matrix-results.json](matrix-results.json) contains allowlisted measurements for all 112 planned ledger attempts. It includes treatment identities, correctness, terminal status, native usage totals/components and coverage, tool/source-changing counts, source size, and receipt/report commitments. Unknown values remain `null`.

It excludes prompts, provider response bodies, account identifiers, credentials, local filesystem paths, candidate source and operational logs. The full raw `results/` tree and qualified Docker image are **not distributed** in this repository. A hash commits to an original artifact but cannot let a reader independently inspect an artifact they do not have. Published measurements support recomputing aggregate tables; they do not substitute for raw-trace or candidate-source verification.

Recompute the overview without Docker or subscriptions:

```sh
python3 scripts/export_public_results.py --summary docs/data/matrix-results.json
python3 -m unittest tests.test_public_results
```

On the original machine, reproduce or check the export against the three closed, separately validated reports:

```sh
python3 scripts/export_public_results.py \
  results/subscription-matrix-final/analysis.json \
  results/opus-medium-matrix-final/analysis.json \
  results/sol-medium-matrix-final/analysis.json \
  --output docs/data/matrix-results.json --check
```

Omit `--check` to write a new export. Do not overwrite historical measurements when running a new campaign; publish it under a distinct name with its own provenance. Raw reports can be regenerated with the analysis commands in [the tutorial](../setup.md#analyze-and-resume).

Source report SHA-256 values are preserved in the JSON. Existing research documents may name `results/...` files as local provenance; those paths are not downloads. Trace audits describe observations from the original local receipts. The queue's separately published sanitized measurements are [queue-load-validation.json](../queue-load-validation.json).
