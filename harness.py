"""Bounded synthetic escrow state machine and an independent event-fold oracle.

This module is deliberately stdlib-only. StateModel is the command-side model;
IndependentLiabilityOracle never reads its fields or imports its implementation.
"""
from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass

CREATORS = tuple(f"creator-{i}" for i in range(3))
WORKERS = tuple(f"worker-{i}" for i in range(5))
OPERATORS = tuple(f"operator-{i}" for i in range(3))
RECIPIENTS = tuple(f"recipient-{i}" for i in range(5))


def stable_hash(text: str) -> str:
    return "0x" + hashlib.sha256(text.encode()).hexdigest()


def generate_sequence(seed: int, depth: int = 100) -> list[dict]:
    """Generate exactly depth deterministic calls, including three creations."""
    if depth < 3:
        raise ValueError("depth must be at least three")
    rng = random.Random(seed)
    actions = [
        {"op": "create", "bid": f"b{seed}-0", "creator": CREATORS[0], "amount": 10 + seed % 41, "deadline": 3},
        {"op": "create", "bid": f"b{seed}-1", "creator": CREATORS[1], "amount": 15 + seed % 37, "deadline": 4},
        {"op": "create", "bid": f"b{seed}-2", "creator": CREATORS[2], "amount": 20 + seed % 29, "deadline": 5},
    ]
    bids = [f"b{seed}-{i}" for i in range(3)]
    for step in range(3, depth):
        bid = rng.choice(bids)
        creator = CREATORS[int(bid[-1])]
        choice = rng.randrange(10)
        if choice == 0:
            actions.append({"op": "time", "amount": rng.randrange(1, 5)})
        elif choice == 1:
            actions.append({"op": "delegate", "creator": creator, "operator": OPERATORS[int(bid[-1])]})
        elif choice in (2, 3):
            actions.append({"op": "topup", "bid": bid, "amount": 1 + rng.randrange(20), "actor": creator})
        elif choice in (4, 5):
            actions.append({"op": "award", "bid": bid, "winner": rng.choice(WORKERS), "actor": rng.choice((creator, OPERATORS[int(bid[-1])], "attacker"))})
        elif choice == 6:
            actions.append({"op": "cancel", "bid": bid, "actor": rng.choice((creator, OPERATORS[int(bid[-1])], "attacker"))})
        elif choice == 7:
            actions.append({"op": "withdraw", "account": rng.choice(WORKERS + CREATORS), "recipient": rng.choice(RECIPIENTS), "fail": False})
        elif choice == 8:
            actions.append({"op": "withdraw", "account": rng.choice(WORKERS + CREATORS), "recipient": rng.choice(RECIPIENTS), "fail": True})
        else:
            actions.append({"op": "donate", "amount": 1 + rng.randrange(12)})
    return actions


@dataclass
class Bounty:
    creator: str
    locked: int
    deadline: int
    terminal: bool = False


class StateModel:
    """Small command model; no oracle code is shared with the checker."""
    def __init__(self, seed: int = 0, mutation: bool = False):
        self.seed = seed
        self.mutation = mutation
        self.now = 0
        self.bounties: dict[str, Bounty] = {}
        self.credits: dict[str, int] = {}
        self.operators: dict[str, str] = {}
        self.balance = 0
        self.events: list[dict] = []
        self.attempts = 0

    def _emit(self, kind: str, **data):
        self.events.append({"kind": kind, **data})

    def create(self, bid: str, creator: str, amount: int, deadline: int):
        if bid in self.bounties or amount <= 0:
            raise ValueError("invalid create")
        self.bounties[bid] = Bounty(creator, amount, deadline)
        self.balance += amount
        self._emit("create", bid=bid, creator=creator, amount=amount)

    def _authorized(self, b: Bounty, actor: str) -> bool:
        return actor == b.creator or self.operators.get(b.creator) == actor

    def award(self, bid: str, winner: str, actor: str):
        b = self.bounties[bid]
        if not self._authorized(b, actor):
            raise ValueError("unauthorized")
        if b.terminal and not self.mutation:
            raise ValueError("terminal")
        if b.terminal and self.mutation:
            # Deliberate local mutation: terminal awards pay again.
            amount = b.locked
            self.credits[winner] = self.credits.get(winner, 0) + amount
            self.balance += amount
            self._emit("award", bid=bid, creator=b.creator, winner=winner, amount=amount)
            return
        amount = b.locked
        b.locked = 0
        b.terminal = True
        self.credits[winner] = self.credits.get(winner, 0) + amount
        self._emit("award", bid=bid, creator=b.creator, winner=winner, amount=amount)

    def cancel(self, bid: str, actor: str):
        b = self.bounties[bid]
        if not self._authorized(b, actor) or b.terminal or self.now <= b.deadline + 7:
            raise ValueError("not cancellable")
        amount = b.locked
        b.locked = 0
        b.terminal = True
        self.credits[b.creator] = self.credits.get(b.creator, 0) + amount
        self._emit("cancel", bid=bid, creator=b.creator, amount=amount)

    def topup(self, bid: str, amount: int, actor: str):
        b = self.bounties[bid]
        if not self._authorized(b, actor) or b.terminal or amount <= 0:
            raise ValueError("invalid topup")
        b.locked += amount
        self.balance += amount
        self._emit("topup", bid=bid, amount=amount)

    def withdraw(self, account: str, recipient: str, fail: bool = False):
        self.attempts += 1
        amount = self.credits.get(account, 0)
        if amount <= 0:
            raise ValueError("no credit")
        if fail:
            return False
        self.credits[account] = 0
        self.balance -= amount
        self._emit("withdraw", account=account, recipient=recipient, amount=amount)
        return True

    def apply(self, action: dict):
        op = action["op"]
        if op == "create": return self.create(action["bid"], action["creator"], action["amount"], action["deadline"])
        if op == "time": self.now += action["amount"]; return None
        if op == "delegate": self.operators[action["creator"]] = action["operator"]; return None
        if op == "topup": return self.topup(action["bid"], action["amount"], action["actor"])
        if op == "award": return self.award(action["bid"], action["winner"], action["actor"])
        if op == "cancel": return self.cancel(action["bid"], action["actor"])
        if op == "withdraw": return self.withdraw(action["account"], action["recipient"], action["fail"])
        if op == "donate": self.balance += action["amount"]; self._emit("donate", amount=action["amount"]); return None
        raise ValueError(f"unknown operation {op}")

    def snapshot(self) -> dict:
        locked = {bid: b.locked for bid, b in self.bounties.items()}
        credits = {k: v for k, v in self.credits.items() if v}
        liabilities = sum(locked.values()) + sum(credits.values())
        return {"locked": locked, "credits": credits, "liabilities": liabilities, "balance": self.balance}


class IndependentLiabilityOracle:
    """Reconciles receipts from scratch, with no StateModel imports or fields."""

    @staticmethod
    def _validate_money(value, label: str, *, positive: bool = False) -> int:
        if type(value) is not int:
            raise AssertionError(f"invalid {label}: monetary values must be exact integers")
        if (value <= 0) if positive else (value < 0):
            expectation = "positive" if positive else "non-negative"
            raise AssertionError(f"invalid {label}: monetary values must be {expectation}")
        return value

    def reconcile(self, events: list[dict], snapshot: dict) -> int:
        snapshot_locked = snapshot["locked"]
        snapshot_credits = snapshot["credits"]
        self._validate_money(snapshot["liabilities"], "snapshot liabilities")
        self._validate_money(snapshot["balance"], "snapshot balance")
        for bid, amount in snapshot_locked.items():
            self._validate_money(amount, f"snapshot locked[{bid!r}]")
        for account, amount in snapshot_credits.items():
            self._validate_money(amount, f"snapshot credits[{account!r}]")

        locked: dict[str, int] = {}
        creators: dict[str, str] = {}
        settled: set[str] = set()
        credits: dict[str, int] = {}
        balance = 0
        for event in events:
            kind = event["kind"]
            if kind == "create":
                amount = self._validate_money(event["amount"], "create amount", positive=True)
                if event["bid"] in locked:
                    raise AssertionError("duplicate create")
                locked[event["bid"]] = amount
                creators[event["bid"]] = event["creator"]
                balance += amount
            elif kind == "topup":
                amount = self._validate_money(event["amount"], "topup amount", positive=True)
                if event["bid"] not in locked or event["bid"] in settled:
                    raise AssertionError("topup after terminal")
                locked[event["bid"]] += amount
                balance += amount
            elif kind in ("award", "cancel"):
                amount = self._validate_money(event["amount"], f"{kind} amount", positive=True)
                bid = event["bid"]
                if bid not in locked or bid in settled or locked[bid] != amount:
                    raise AssertionError("terminal bounty paid twice or amount mismatch")
                wallet = event["winner"] if kind == "award" else event["creator"]
                if event["creator"] != creators[bid]:
                    raise AssertionError("creator mismatch")
                credits[wallet] = credits.get(wallet, 0) + amount
                locked[bid] = 0
                settled.add(bid)
            elif kind == "withdraw":
                amount = self._validate_money(event["amount"], "withdraw amount", positive=True)
                account = event["account"]
                if credits.get(account, 0) != amount:
                    raise AssertionError("invalid withdrawal")
                credits[account] = 0
                balance -= amount
            elif kind == "donate":
                amount = self._validate_money(event["amount"], "donate amount", positive=True)
                balance += amount
            else:
                raise AssertionError(f"unknown event {kind}")
        locked = {k: v for k, v in locked.items()}
        credits = {k: v for k, v in credits.items() if v}
        liability = sum(locked.values()) + sum(credits.values())
        if {"locked": locked, "credits": credits, "liabilities": liability, "balance": balance} != snapshot:
            raise AssertionError("snapshot differs from independently folded receipts")
        if balance < liability:
            raise AssertionError("token balance below independent liabilities")
        return liability


def run_mutation_probe() -> bool:
    model = StateModel(seed=999, mutation=True)
    model.create("mutant", "creator-0", 10, 0)
    model.award("mutant", "worker-0", "creator-0")
    model.award("mutant", "worker-1", "creator-0")
    try:
        IndependentLiabilityOracle().reconcile(model.events, model.snapshot())
    except AssertionError:
        return True
    return False
