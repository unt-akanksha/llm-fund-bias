"""Own-maker lift: popularity shared by all models cancels; a planted own-maker boost is detected."""

import json

import numpy as np
import pandas as pd

import analyze_stage1 as A


def synthetic(n=200, seed=0):
    """Model 'a' names X 60% of the time vs 20% for 'b'; both name POP 80% of the time."""
    rng = np.random.default_rng(seed)
    rows = []
    for mk, p_x in [("a", 0.6), ("b", 0.2)]:
        for i in range(n):
            cs = [c for c, p in [("X", p_x), ("POP", 0.8)] if rng.random() < p]
            rows.append({"model_key": mk, "prompt_id": f"p{i % 4}", "companies": cs})
    return pd.DataFrame(rows)


def test_lift_detects_planted_boost_and_ignores_popularity(monkeypatch):
    monkeypatch.setattr(A, "N_PERM", 500)
    monkeypatch.setattr(A, "N_BOOT", 300)
    df = synthetic(n=1000)
    M = A.mention_matrix(df)
    t, joint = A.lift_table(df, M, [("a", "X", "primary"), ("a", "POP", "primary")])
    x, pop = t.iloc[0], t.iloc[1]
    assert 30 < x.lift_pp < 50 and x.lift_lo_pp > 0 and x.p_fisher < 1e-6 and x.p_perm_one_sided < 0.01
    assert abs(pop.lift_pp) < 5 and pop.lift_lo_pp < 0 < pop.lift_hi_pp and pop.p_perm_two_sided > 0.05
    assert joint["sum_lift_pp"] == x.lift_pp + pop.lift_pp


def test_permutation_keeps_labels_within_prompt():
    df = synthetic(n=40)
    pm = A.permute_within(df.model_key, df.prompt_id, np.random.default_rng(1))
    assert pd.crosstab(df.prompt_id, pm).equals(pd.crosstab(df.prompt_id, df.model_key))
    assert not pm.equals(df.model_key)


def test_mention_matrix_excludes_etf_and_unknown():
    df = pd.DataFrame({"companies": [["META", "ETF:VOO"], ["UNKNOWN:x", "BABA"]]})
    assert list(A.mention_matrix(df).columns) == ["BABA", "META"]
