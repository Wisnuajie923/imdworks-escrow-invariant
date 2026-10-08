"""One-command bounded invariant corpus runner."""
from __future__ import annotations

import json
import platform
import shutil
import subprocess
import sys
from pathlib import Path

from harness import IndependentLiabilityOracle, StateModel, generate_sequence, run_mutation_probe

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "generated"
TRACE = OUT / "trace.jsonl"
REPORT = OUT / "report.json"
SEQUENCES = 1000
DEPTH = 100
BASE_SEED = 606006  # fixed, documented seed (no ambient entropy)


def run() -> int:
    OUT.mkdir(exist_ok=True)
    test = subprocess.run([sys.executable, "-m", "unittest", "-v"], cwd=ROOT, text=True, capture_output=True)
    (OUT / "unit-tests.log").write_text(test.stdout + test.stderr)
    records = []
    reconciled = 0
    rejected_calls = 0
    failures = []
    oracle = IndependentLiabilityOracle()
    for sequence_id in range(SEQUENCES):
        seed = BASE_SEED + sequence_id
        model = StateModel(seed=seed)
        actions = generate_sequence(seed, DEPTH)
        accepted = 0
        rejected = []
        for index, action in enumerate(actions):
            try:
                model.apply(action)
                accepted += 1
            except (KeyError, ValueError) as exc:
                rejected_calls += 1
                rejected.append({"index": index, "op": action["op"], "reason": str(exc)})
        try:
            liability = oracle.reconcile(model.events, model.snapshot())
            reconciled += 1
            records.append({
                "sequence": sequence_id,
                "seed": seed,
                "depth": DEPTH,
                "status": "ok",
                "accepted_calls": accepted,
                "rejected_calls": len(rejected),
                "event_count": len(model.events),
                "independent_liabilities": liability,
                "token_balance": model.snapshot()["balance"],
                "actions": actions,
                "rejections": rejected,
            })
        except Exception as exc:
            failures.append({"sequence": sequence_id, "seed": seed, "error": f"{type(exc).__name__}: {exc}"})
            records.append({"sequence": sequence_id, "seed": seed, "depth": DEPTH, "status": "error", "error": str(exc), "actions": actions})
    TRACE.write_text("".join(json.dumps(record, sort_keys=True, separators=(",", ":")) + "\n" for record in records))
    mutation_detected = run_mutation_probe()
    report = {
        "schema": 1,
        "status": "PASS" if test.returncode == 0 and not failures and reconciled == SEQUENCES and mutation_detected else "FAIL",
        "implementation": "bounded Python stdlib synthetic state machine; Foundry/anvil unavailable on runner",
        "python_version": platform.python_version(),
        "foundry_available": shutil.which("forge") is not None,
        "deterministic_seed": BASE_SEED,
        "seed_formula": "BASE_SEED + sequence_id",
        "requested_sequences": SEQUENCES,
        "generated_sequences": len(records),
        "sequence_depth": DEPTH,
        "reconciled_ok": reconciled,
        "reconciliation_failures": len(failures),
        "rejected_calls_total": rejected_calls,
        "unit_tests_returncode": test.returncode,
        "unit_tests_passed": test.returncode == 0,
        "unit_test_count": 5,
        "broken_mutation": "terminal award pays a second time",
        "broken_mutation_detected": mutation_detected,
        "trace_records": len(records),
        "failures": failures,
        "limitations": [
            "No Solidity compiler, Foundry, Anvil, RPC, wallet, credentials, or network was used.",
            "The model is a bounded local behavioral approximation, not deployed-bytecode execution or a formal proof.",
            "The oracle folds emitted receipts independently and does not import StateModel state or implementation logic.",
        ],
    }
    REPORT.write_text(json.dumps(report, sort_keys=True, indent=2) + "\n")
    print(json.dumps({k: report[k] for k in ("status", "generated_sequences", "sequence_depth", "reconciled_ok", "reconciliation_failures", "broken_mutation_detected", "unit_tests_returncode")}, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(run())
