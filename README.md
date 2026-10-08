# Bounty #6 — stateful escrow accounting invariant harness

Offline, bounded invariant harness for `bb5bb8eb-14e4-4f07-b86e-565ab2c37972`.

## Reproduce

From this directory, run exactly one command:

```sh
python3 run_tests.py
```

The runner currently executes **1,000 deterministic sequences at depth 100** (100 command calls per sequence), then writes:

- `generated/trace.jsonl`: exactly one JSON record per sequence, including seed, all generated actions, accepted/rejected calls, event count, independently folded liabilities, and token balance.
- `generated/report.json`: stable machine-readable counts, tool/runtime details, mutation result, and limitations.
- `generated/unit-tests.log`: output from the focused three-test unittest suite.

The command exits non-zero on a unit-test failure, reconciliation failure, short corpus, or undetected mutation.

## What is tested

Each sequence starts three synthetic bounties for three creators and then explores awards, delegated operators, top-ups, time jumps, cancellation after the seven-day review window, withdrawals (including failed attempts), and donations. Five worker identities are used as winners. Calls that are invalid for the current state are recorded as bounded rejected calls; they do not end the sequence.

`StateModel` owns command-side state and receipt emission. `IndependentLiabilityOracle` folds receipts from scratch: it tracks each bounty's locked amount, terminal status, creator, credits, inflows/outflows, and computes `locked + claimable` independently. It asserts that the reported token balance covers this liability and rejects a terminal bounty being settled twice. The oracle does not import or inspect model state.

The negative control enables a local mutation in which a terminal bounty can be awarded again. The oracle rejects the resulting duplicate terminal payment; the report records `broken_mutation_detected: true`.

The oracle also applies strict monetary-domain validation at its receipt boundary: create, top-up, award, cancel, donate, and withdrawal amounts must be exact positive integers (booleans and floats are rejected), while snapshot locked amounts, credits, liabilities, and balance must be exact non-negative integers.

## Tool and evidence boundary

This host does not provide `forge` or `anvil`, so this is an honest Python 3.12 stdlib harness rather than a Foundry/local-EVM execution. No RPC, network, wallet, credential, signing, production contract write, bounty claim, or external submission is performed. This proves the stated properties for the synthetic state machine and receipt format, not deployed Solidity bytecode correctness or formal verification.

The seed is fixed at `606006`; sequence `n` uses `606006 + n`. Outputs are regenerated rather than accumulated. See `TDD.md` for red/green evidence and `SIGNOFF.md` for acceptance mapping.
