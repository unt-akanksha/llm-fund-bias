"""Stage 2: pick parsing, balanced design, and the logistic regression on synthetic data."""

import json
from collections import Counter

import numpy as np
import pandas as pd

import analyze_stage2 as A
import stage2_design as S2
from run_stage2 import parse_pick

CFG, PR = S2.load()
REAL, FICT = CFG["companies"], CFG["fictional"]


def test_parse_pick_ticker_name_and_failures():
    assert parse_pick(json.dumps({"reasoning": "x", "ticker": "META"}), REAL) == (0, "META")
    assert parse_pick(json.dumps({"reasoning": "x", "ticker": "NASDAQ: msft"}), REAL)[0] == 2
    assert parse_pick(json.dumps({"reasoning": "x", "ticker": "Alibaba Group"}), REAL)[0] == 1
    assert parse_pick(json.dumps({"reasoning": "x", "ticker": "NRVQ"}), FICT)[0] == 0
    assert parse_pick(json.dumps({"reasoning": "x", "ticker": "META"}), FICT)[0] is None   # real ticker in control
    assert parse_pick("not json", REAL)[0] is None


def test_design_is_balanced_and_conditions_match():
    n = CFG["runs_per_condition"]
    counts = Counter((j, r) for i in range(n) for j, r in S2.plan(CFG, i)[0].items())
    assert set(counts.values()) == {5} and len(counts) == 100
    for i in range(3):   # same numbers and row order in both conditions; only names differ
        real, _, _ = S2.table(CFG, PR, i, "real_names")
        fict, _, _ = S2.table(CFG, PR, i, "fictional_names")
        strip = lambda t: [line.split("|")[3:] for line in t.splitlines()[2:]]  # noqa: E731
        assert strip(real) == strip(fict)
    assert "All figures are hypothetical." in S2.messages(CFG, PR, 0, "real_names")[0][1]["content"]


def test_logit_recovers_planted_own_effect_and_rank(monkeypatch):
    monkeypatch.setattr(A, "own_company", lambda mk: ("META", "primary"))
    rng = np.random.default_rng(0)
    rows = []
    for i in range(300):
        ranks, order = S2.plan(CFG, i % 50)
        util = np.array([-0.5 * ranks[j] + (1.5 if j == 0 else 0) for j in range(10)])  # slot 0 = META
        p = np.exp(util) / np.exp(util).sum()
        rows.append({"run_id": f"r{i}", "model_key": "m", "condition": "real_names",
                     "chosen_slot": int(rng.choice(10, p=p)), "ranks_by_slot": [ranks[j] for j in range(10)],
                     "row_order_slots": order})
    L = A.long_table(pd.DataFrame(rows), CFG)
    res = A.fit(L)
    assert res.params["is_own_maker"] > 0.8 and res.pvalues["is_own_maker"] < 0.001
    assert res.params["financial_rank"] < -0.3 and abs(res.params["row_position"]) < 0.15
