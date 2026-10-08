import unittest

from harness import IndependentLiabilityOracle, StateModel, generate_sequence


class HarnessTests(unittest.TestCase):
    def test_sequence_reconciles_independently(self):
        model = StateModel(seed=7)
        actions = generate_sequence(7, depth=100)
        for action in actions:
            try:
                model.apply(action)
            except (KeyError, ValueError):
                pass
        observed = IndependentLiabilityOracle().reconcile(model.events, model.snapshot())
        self.assertEqual(observed, model.snapshot()["liabilities"])

    def test_terminal_bounty_cannot_pay_twice(self):
        model = StateModel(seed=11)
        model.create("b0", "creator-0", 10, 0)
        model.award("b0", "worker-0", "creator-0")
        with self.assertRaises(ValueError):
            model.award("b0", "worker-1", "creator-0")

    def test_broken_mutation_is_detected(self):
        from harness import run_mutation_probe
        self.assertTrue(run_mutation_probe())

    def test_oracle_rejects_non_positive_or_non_integer_event_amounts(self):
        oracle = IndependentLiabilityOracle()
        cases = [
            ([{"kind": "create", "bid": "b0", "creator": "c", "amount": amount}],
             {"locked": {"b0": amount}, "credits": {}, "liabilities": amount, "balance": amount})
            for amount in (0, -1, 1.5, True)
        ]
        cases += [
            ([{"kind": "create", "bid": "b0", "creator": "c", "amount": 1}, {"kind": "topup", "bid": "b0", "amount": amount}],
             {"locked": {"b0": 1 + amount}, "credits": {}, "liabilities": 1 + amount, "balance": 1 + amount})
            for amount in (0, -1, 1.5, True)
        ]
        cases += [
            ([{"kind": "create", "bid": "b0", "creator": "c", "amount": 1}, {"kind": "award", "bid": "b0", "creator": "c", "winner": "w", "amount": amount}],
             {"locked": {"b0": 0}, "credits": {"w": amount}, "liabilities": amount, "balance": 1})
            for amount in (0, -1, 1.5, True)
        ]
        cases += [
            ([{"kind": "create", "bid": "b0", "creator": "c", "amount": 1}, {"kind": "cancel", "bid": "b0", "creator": "c", "amount": amount}],
             {"locked": {"b0": 0}, "credits": {"c": amount}, "liabilities": amount, "balance": 1})
            for amount in (0, -1, 1.5, True)
        ]
        cases += [
            ([{"kind": "donate", "amount": amount}],
             {"locked": {}, "credits": {}, "liabilities": 0, "balance": amount})
            for amount in (0, -1, 1.5, True)
        ]
        cases += [
            ([{"kind": "withdraw", "account": "w", "recipient": "r", "amount": amount}],
             {"locked": {}, "credits": {}, "liabilities": 0, "balance": -amount})
            for amount in (0, -1, 1.5, True)
        ]
        for events, snapshot in cases:
            with self.subTest(events=events):
                with self.assertRaises(AssertionError):
                    oracle.reconcile(events, snapshot)

    def test_oracle_rejects_malformed_snapshot_monetary_values(self):
        oracle = IndependentLiabilityOracle()
        events = [{"kind": "create", "bid": "b0", "creator": "c", "amount": 1}]
        for field, value in (
            ("locked", {"b0": -1}),
            ("locked", {"b0": 1.5}),
            ("credits", {"w": -1}),
            ("credits", {"w": 1.5}),
            ("balance", -1),
            ("balance", 1.5),
        ):
            with self.subTest(field=field, value=value):
                snapshot = {"locked": {"b0": 1}, "credits": {}, "liabilities": 1, "balance": 1}
                snapshot[field] = value
                with self.assertRaises(AssertionError):
                    oracle.reconcile(events, snapshot)


if __name__ == "__main__":
    unittest.main()
