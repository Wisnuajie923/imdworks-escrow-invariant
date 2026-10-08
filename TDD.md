# TDD log

This repository keeps command output from real test executions in `evidence/`.

## RED — tdd-01-red.log

Tests were written first and executed before `harness.py` existed:

```text
python3 -m unittest -v
```

Observed result: import failure, `ModuleNotFoundError: No module named 'harness'`, non-zero exit. This is the authentic initial red state, not a simulated transcript.

## GREEN — tdd-02-green.log

After implementing the model, independent oracle, mutation probe, and runner:

```text
python3 -m unittest -v
```

Observed result: the original 3 tests ran and passed. The log is captured directly from the command.

## RED — focused oracle monetary probes

The regression probes were then added before the fix and executed against the unfixed oracle:

```text
python3 -m unittest -v
```

Observed result: 13 subtests failed because negative, zero, float, and boolean event amounts were accepted; the existing tests still passed. This was the authentic blocker-specific red state.

## GREEN — strict monetary validation

After the minimal oracle validation fix:

```text
python3 -m unittest -v
```

Observed result: 5 tests ran and passed, including the event-amount and malformed-snapshot regression probes. The captured output is `evidence/tdd-03-green-oracle-validation.log`.

## Acceptance execution

```text
python3 run_tests.py
```

Observed result: 1,000 sequences generated, each depth 100; 1,000 independently reconciled; zero reconciliation failures; broken mutation detected; unit-test return code 0; process exit 0. The fresh machine-readable result is `generated/report.json`, and the per-sequence evidence is `generated/trace.jsonl`. The captured command output is `evidence/tdd-04-green-full-run.log`.

The final runner uses only fixed seed arithmetic and Python standard library facilities. It does not rely on wall-clock time or external services.
