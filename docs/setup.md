# Setup and benchmark tutorial

Run commands from the repository root. Start with the no-inference checks, then qualify the runtime, then qualify a provider and run one development attempt. Full matrices are optional, quota-consuming experiments.

## What is included

| Track | Implemented | Interpretation |
|---|---|---|
| Ledger coding | Seven native ports, T0/T1, isolated grading, four subscription adapters, matrix runners | Completed exploratory campaign; one task, no general language ranking |
| Crash store / protocol migration | Ruby/Rust smoke controls | Small development controls, not frontier tasks |
| Queue runtime | RabbitMQ, durable sink, four reference worker stacks, fault scenarios | Infrastructure-limited development trials, not qualified sustainable capacity |
| Queue AI-effort / stronger pressure | Research protocol | Not implemented as a controlled model matrix |

The checkout contains source, tests, contracts, references, plans and [sanitized historical measurements](data/README.md). It does **not** contain raw historical traces, subscription credentials, installed provider CLIs, vendored build dependencies, or the historical Docker image. Historical `results/...` paths in documents refer to the original machine.

## 1. Controller setup, no inference

Use Python 3.11+ and Git. The controller uses the Python standard library. Packaging needs setuptools and wheel; queue Python dependencies are installed inside the trusted infrastructure image, not in the host environment.

```sh
git clone https://github.com/akitaonrails/vibe-coding-benchmarks.git
cd vibe-coding-benchmarks
python3 -m venv .venv
source .venv/bin/activate
python -m pip install 'setuptools>=68' wheel
python -m pip install --no-build-isolation --no-deps -e .
mkdir -p .work results

python -m langbench list
python scripts/export_public_results.py --summary docs/data/matrix-results.json
python -m unittest tests.test_public_results tests.test_subscription_analysis_script tests.test_later_analysis_script
```

Use the source checkout for experiments: matrix plans and analysis scripts are repository files. The installation also provides `langbench` and `queuebench` entry points. These steps make no model calls. Installing Python build tools may access the network.

Prepare two new workspaces:

```sh
python -m langbench prepare ledger_engine ruby .work/tutorial-ruby-t1 --tests T1
python -m langbench prepare ledger_engine rust .work/tutorial-rust-t0 --tests T0
```

Each destination must not already exist. T1 includes `TASK.md`, a working starter, public histories and a driver; T0 withholds the supplied histories/driver. Both allow agents to write tests. Only `src/` is submitted; the grader restores trusted build/configuration files. Preparation itself requires neither Docker nor native compilers.

## 2. Linux and the seven-language Docker runtime

Candidate execution requires a Linux Docker Engine with working cgroup CPU/memory/PID controls and access to its socket from the controller. Budget at least the candidate's two CPUs and 4 GiB, plus controller/host headroom and substantial compiler-image disk space. The runtime tests fail closed if requested boundaries are not enforced; macOS, Windows and rootless setups are not qualified by this campaign.

Check Docker, then inspect the image selected by the repository:

```sh
docker version
docker info
python - <<'PY'
import json, subprocess
from pathlib import Path
config = json.loads(Path('configs/toolchain-seven.json').read_text())
subprocess.run(['docker', 'image', 'inspect', config['image']], check=True)
PY
```

The configured `sha256:...` is a local immutable **image ID**, not a registry pull address. On a fresh machine it will normally be absent. There is no published image archive in this repository. Use a separately supplied original archive (`docker load -i PATH`) for exact-image reuse, or build and qualify a **new runtime** as follows.

### Build a new runtime

The build host needs Cargo and an acquired Gson 2.11.0 JAR. The Docker build installs the other compilers. Network access is allowed during dependency acquisition and image building; candidate execution remains offline. Use only the small build context below, never the whole repository.

```sh
mkdir -p .runtime-build
cargo vendor --locked --manifest-path tasks/ledger_engine/references/rust/Cargo.toml .runtime-build/cargo-vendor
# Set this to a locally acquired Gson 2.11.0 JAR:
export BENCH_GSON_JAR=/absolute/path/to/gson-2.11.0.jar
python - <<'PY'
import hashlib, json, os, shutil
from pathlib import Path
source = Path(os.environ['BENCH_GSON_JAR'])
config = json.loads(Path('configs/toolchain-seven.json').read_text())
assert hashlib.sha256(source.read_bytes()).hexdigest() == config['gson_sha256'], 'Gson checksum mismatch'
shutil.copyfile(source, '.runtime-build/gson.jar')
shutil.copyfile('toolchains/seven/Dockerfile', '.runtime-build/Dockerfile')
PY
docker build -t langbench-seven:dev .runtime-build
```

The base image is pinned, but the Dockerfile uses rolling Arch mirrors. This recipe does **not** promise the historical package closure or image ID. Compare the new inventory to [packages.lock](../toolchains/seven/packages.lock). On your new experiment branch, save the original configuration and bind the newly built image:

```sh
git switch -c experiment/local-runtime
python - <<'PY'
import hashlib, json, subprocess
from pathlib import Path
path = Path('configs/toolchain-seven.json')
original = path.read_bytes()
with Path('.work/toolchain-seven-original.json').open('xb') as handle:
    handle.write(original)
config = json.loads(original)
image = subprocess.check_output(['docker', 'image', 'inspect', '--format', '{{.Id}}', 'langbench-seven:dev'], text=True).strip()
inventory = subprocess.check_output(['docker', 'run', '--rm', '--network', 'none', image, 'cat', '/opt/toolchain-packages.lock'])
Path('.work/toolchain-packages.lock').write_bytes(inventory)
config.update(image=image, packages_sha256=hashlib.sha256(inventory).hexdigest())
path.write_text(json.dumps(config, indent=2) + '\n')
print('New runtime:', image)
print('Matches historical package inventory:', inventory == Path('toolchains/seven/packages.lock').read_bytes())
PY
```

Recording an image hash is not qualification. Run the boundaries and native reference checks before collecting candidates:

```sh
python -m unittest tests.test_seven_runtime tests.test_packaging
python -m langbench selftest --runtime seven > results/local-reference-selftest.json
```

`selftest` grades references in all supported task/language combinations and returns nonzero on any failure. It consumes no LLM quota. Fix toolchain incompatibilities before going further; preserve the new package inventory, runtime config and validation evidence with your experiment. A changed closure is a different instrumentation cohort, even if reference checks pass. See [runtime provenance](../toolchains/seven/README.md).

For a manual development submission:

```sh
python -m langbench grade ledger_engine ruby .work/tutorial-ruby-t1 --runtime seven
```

The unmodified starter is expected to fail the full task. Grading returns exit code 1 for a failing submission. Use the Docker backend (the default) for candidates; `trusted-reference` is not candidate isolation. Do not mount this repository, credentials, Docker socket, oracle or references into an agent's workspace. The source-public grader is private **during a trial**; fresh held-out task instances are needed for future confirmatory work.

## 3. Provider prerequisites

These are the exact campaign configurations, not promises that every account or future CLI exposes these identifiers:

| Provider key | Model / effort | CLI version and default executable | Existing account state |
|---|---|---|---|
| `kimi` | `kimi-code/k3` / high | 2.1.1, `~/.kimi-code/bin/kimi` | Managed Kimi OAuth configuration and canonical credential/lock directories |
| `opencode` | `zai/glm-5.3` / high | 1.18.34, `~/.local/share/mise/installs/opencode/1.18.34/opencode` | Z.ai **coding-plan** route configured in OpenCode, credential referenced from an environment variable |
| `claude` | `claude-opus-5-5` / medium | 2.1.290, `~/.local/share/mise/installs/claude/2.1.290/claude` | Canonical Claude Pro/Max OAuth login, extra usage disabled |
| `codex` | `gpt-6-sol` / medium | 0.156.0, `~/.local/share/mise/installs/codex/0.156.0/bin/codex` | Existing ChatGPT subscription login; matching `codex-code-mode-host` alongside the binary |

Install/authenticate the exact CLI using its own supported setup before qualification. Credentials stay outside the repository. Native provider login commands are not run automatically by this tutorial. Kimi/OpenCode routes are enforced in [provider_cli.py](../langbench/provider_cli.py); Claude also enforces an exact binary hash in [claude_subscriptions.py](../langbench/claude_subscriptions.py); Codex checks effective capabilities and subscription allowance through [codex_subscriptions.py](../langbench/codex_subscriptions.py).

Kimi expects `~/.kimi-code/config.toml` to select its managed OAuth coding route. OpenCode expects `~/.config/opencode/opencode.json` provider `zai` with `npm: @ai-sdk/openai-compatible`, `baseURL: https://api.z.ai/api/coding/paas/v4`, and an `apiKey` reference such as `{env:ZAI_CODING_API_KEY}` whose variable is already set. That credential must belong to the coding subscription. Claude excludes ambient API-key settings and retains canonical OAuth refresh state; Codex uses `~/.codex/auth.json` without inheriting the user's tool configuration.

Different versions, models or routes require adapter review, boundary/usage tests and fresh live qualification. Do not remove a version/hash check to make a run proceed. Python single-run APIs accept `binary=Path(...)`, but full matrix CLIs use default paths; custom installations need a documented adapter-path change before qualification and plan freeze. Do not substitute an available model and retain the old label.

## 4. Qualify one provider, then run one development attempt

**These commands consume your subscription allowance.** Choose one provider; the block qualifies only that provider. It verifies the effective model/effort, tool isolation, resumed session and usage accounting. Passing qualification is not a candidate-correctness result. Use new output directories for subsequent trials.

```sh
export BENCH_PROVIDER=codex  # choose kimi, opencode, claude, or codex
python - <<'PY'
import os
from langbench.subscriptions import qualify_provider
from langbench.claude_subscriptions import qualify_claude
from langbench.codex_subscriptions import qualify_codex
provider = os.environ['BENCH_PROVIDER']
destination = f'results/local-qualification-{provider}'
qualifiers = {
    'kimi': lambda: qualify_provider('kimi', destination, model='kimi-code/k3', effort='high'),
    'opencode': lambda: qualify_provider('opencode', destination, model='zai/glm-5.3', effort='high'),
    'claude': lambda: qualify_claude(destination),
    'codex': lambda: qualify_codex(destination),
}
receipt = qualifiers[provider]()
print('Qualification passed:', receipt['passed'])
raise SystemExit(0 if receipt['passed'] else 1)
PY
```

Only after a passing receipt:

```sh
python - <<'PY'
import json, os
from pathlib import Path
from langbench.subscriptions import run_subscription
from langbench.claude_subscriptions import run_claude
from langbench.codex_subscriptions import run_codex
provider = os.environ['BENCH_PROVIDER']
model, effort = {'kimi': ('kimi-code/k3', 'high'), 'opencode': ('zai/glm-5.3', 'high'),
                 'claude': ('claude-opus-5-5', 'medium'), 'codex': ('gpt-6-sol', 'medium')}[provider]
qualification = json.loads(Path(f'results/local-qualification-{provider}/qualification.json').read_text())
runner = {'kimi': run_subscription, 'opencode': run_subscription,
          'claude': run_claude, 'codex': run_codex}[provider]
result = runner('ledger_engine', 'ruby', f'results/local-{provider}-ruby-t1',
                provider=provider, model=model, effort=effort, tests='T1', seed=20261010,
                replicate=1, block_id='local-development', base_seconds=900,
                continuation_seconds=180, qualification=qualification)
print('Validity:', result['validity'])
print('Private checkpoint results:', [g.get('success') for g in result.get('grades', [])])
PY
```

This is a separate development attempt, not a replacement for a matrix cell. Inspect `result.json`, `collection/collection.json`, snapshots and the trace directory. Quota/transport failures may leave only partial results; preserve them. Never feed private grading back into a candidate session. The generic `langbench run`/`qualify` commands are the **historical fixed-nudge smoke adapter**, not these adaptive subscription APIs.

## 5. Optional full matrices

Freeze the source, runtime, provider configuration and qualified bindings before starting. No model calls happen when generating plans. Run cohorts sequentially. The defaults are 900 initial seconds plus at most two eligible 180-second nudges: an upper bound of 9.8 active agent-hours for 28 cells or 19.6 for 56, before setup/grading. A subscription does not guarantee capacity for a full run.

For Sol or Opus, use the corresponding passing receipt from step 4:

```sh
python -m langbench.later_matrix plan codex .work/sol-plan.json
python -m langbench.later_matrix run .work/sol-plan.json results/local-sol-matrix --qualification results/local-qualification-codex/qualification.json

# Separately, after qualifying Claude:
python -m langbench.later_matrix plan claude .work/opus-plan.json
python -m langbench.later_matrix run .work/opus-plan.json results/local-opus-matrix --qualification results/local-qualification-claude/qualification.json
```

For the combined Kimi/GLM design, qualify **both** providers first:

```sh
python -m langbench matrix-plan > .work/kimi-glm-plan.json
python -m langbench matrix-run .work/kimi-glm-plan.json results/local-kimi-glm-matrix --kimi-qualification results/local-qualification-kimi/qualification.json --opencode-qualification results/local-qualification-opencode/qualification.json
```

The published Kimi/GLM campaign used legacy retention; Opus/Sol used `seal-v1`. The original Kimi/GLM adapter still defaults to legacy retention. Its historical output-limit classification and timeout artifact limitations are documented in [the first-cohort analysis](subscription-matrix-results.md). New corrective work requires a new instrumentation version and qualifications; it does not retroactively change historical receipts. Historical override records are specific to their receipt hashes and must not be copied into new runs.

### Analyze and resume

Analyze closed matrices into new sibling directories:

```sh
python scripts/analyze_later_matrix.py results/local-sol-matrix results/local-sol-analysis
python scripts/analyze_later_matrix.py results/local-opus-matrix results/local-opus-analysis
python scripts/analyze_subscription_matrix.py results/local-kimi-glm-matrix results/local-kimi-glm-analysis
```

`--allow-interim` explicitly permits an unfinished-cohort report. Keep it labeled interim. The analyzers verify plans, receipt commitments and available snapshot hashes. Complete native usage, partial lower bounds and unknowns remain distinct. [Interpret the outcomes using these definitions](results-summary.md).

After a diagnosed controller/transport incident and verified cleanup, resume the **same** plan and destination with `--resume`, for example:

```sh
python -m langbench.later_matrix run .work/sol-plan.json results/local-sol-matrix --qualification results/local-qualification-codex/qualification.json --resume
```

Only pending cells run. Started/consumed cells are not retried; a previous `running` state becomes `interrupted_unknown`. A quota stop preserves the triggering attempt and marks remaining provider cells unrun. Changing source, qualifications or the plan makes resume fail. Do not erase state or mutate hashes to bypass that check. The repository's successor-fork script exists for the specific reviewed Claude instrumentation migrations; it is not a generic resume override. Automated supervisor support is specific to diagnosed historical incidents, not a license for an unbounded retry loop.

## Queue runtime trials

These commands run real services but no LLM. Use a Linux Docker Engine supporting the runner's isolated IPv4 gateway network mode. Setup downloads RabbitMQ and builds trusted infrastructure; worker images fetch dependencies during their separate build. Run one trial at a time with enough memory/CPU for worker, broker and sink plus host margin. Do not run builds or coding matrices concurrently with measured queue trials.

```sh
python -m scalability.runner setup
docker build -t langbench-queue-elixir:reference scalability/workers/elixir/reference
python -m scalability.runner run langbench-queue-elixir:reference results/local-queue-clean --scenario clean --seed 20261010
```

Other reference contexts are `scalability/workers/{rust,rails,ruby}/reference`; build them with correspondingly named tags. Start with `clean`. Scenarios include `slow`, `lost_response`, `kill_poison`, `broker_restart`, `shutdown` and `handler_crash`. The last needs a source/image-bound hook review to qualify its supervision interpretation; see [the runner documentation](scalability-implementation.md).

To explore the historical sustained-load profile after clean qualification:

```sh
python -m scalability.runner run langbench-queue-elixir:reference results/local-queue-slow --scenario slow --count 10000 --rate 200 --payload-bytes 4096 --seed 20261010 --max-inflight 8 --prefetch 32 --pids 2048 --cpus 2 --memory-mb 1024 --sink-memory-mb 1024 --deadline 90 --drain-seconds 30
```

This is not a qualified capacity comparison. The current corrected runner is also not an exact replay of the historical runner. [Known sink/measurement limits](scalability-load-validation.md) and the [unimplemented stronger pressure protocol](queue-pressure-research.md) must accompany results. The runtime runner does not measure queue-specific AI coding tokens or iterations.

## Troubleshooting and development checks

| Symptom | Action |
|---|---|
| Image ID absent | Load a separately obtained historical archive, or build/bind/qualify a new runtime; `docker pull sha256:...` is not the recipe |
| Package inventory / cgroup mismatch | Check the image and Docker host; keep qualification failures instead of weakening the check |
| Destination already exists | Pick a new destination for independent work; use valid `--resume` only for an existing matrix |
| Frozen input / qualification changed | Restore exact original inputs or start a documented new cohort; never relabel old attempts |
| Exact model, CLI, auth route unavailable | Fix account/installation or qualify a newly labeled configuration; do not substitute silently |
| Claude allowance HTTP 429 | Distinguish status-endpoint throttling from inference quota; preserve preflight timing and proven-unsent records |
| Starter grade fails | Expected: starters intentionally lack required behavior; known-good references must pass |
| Queue network/hook review unqualified | Resolve infrastructure or supply the reviewed hook receipt; a pending review is not a reliability pass |

For controller changes, run focused unit tests. The full suite additionally requires Docker/native dependencies, including historical Ruby/Rust host runtimes for older fixtures; it is not a pure-Python-only command:

```sh
python -m unittest discover -s tests -v
```

Preserve environment receipts, stdout/stderr and exit status for any new validation. Keep credentials and raw provider traces out of commits. Export only reviewed, sanitized fields for publication. Future tasks need independent instances and difficulty calibration before expanding another matrix.
