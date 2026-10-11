"""Gini calculation, plus a smoke test of the shift/order code paths on synthetic data."""

import numpy as np
import pandas as pd
import pytest

from analyze import gini, order_table, rates_table, shifts_table


def test_gini_even_spread_is_zero():
    assert gini([5] * 8) == pytest.approx(0.0)


def test_gini_all_on_one_fund():
    assert gini([40, 0, 0, 0, 0, 0, 0, 0]) == pytest.approx(7 / 8)


def test_gini_known_value_and_scale_invariance():
    # counts [0, 0, 1, 1]: sum|xi-xj| over ordered pairs = 8; 2 * n^2 * mean = 2*16*0.5 = 16 -> 0.5
    assert gini([0, 0, 1, 1]) == pytest.approx(0.5)
    assert gini([3, 1, 0, 0, 0, 0, 0, 4]) == pytest.approx(gini([30, 10, 0, 0, 0, 0, 0, 40]))


def test_gini_empty_is_nan():
    assert np.isnan(gini([0] * 8))


def synthetic(n=100, seed=0):
    """baseline: 90% F1; src_analyst: 40% F1 (rest F3); src_all with ratings position effect."""
    rng = np.random.default_rng(seed)
    rows = []
    for cond, p in [("baseline", 0.9), ("src_analyst", 0.4), ("src_all", None)]:
        for i in range(n):
            rpos = (i % 3) + 1 if cond == "src_all" else np.nan
            prob = p if p is not None else [0.5, 0.7, 0.9][int(rpos) - 1]
            f = "F1" if rng.random() < prob else "F3"
            rows.append({"model_key": "m", "condition_id": cond, "chosen_fund": f, "chose_f1": int(f == "F1"),
                         "chose_f2": 0, "chose_low_fee": int(f == "F1"), "ratings_position": rpos})
    return pd.DataFrame(rows)


def test_shift_detects_large_drop():
    s = shifts_table(synthetic())
    row = s[(s.condition_id == "src_analyst") & (s.measure == "f1")].iloc[0]
    assert -60 < row.shift_pp < -40 and row.p_hc3 < 0.001 and row.ci_lo_pp < row.shift_pp < row.ci_hi_pp


def test_rates_and_order_tables_run():
    df = synthetic()
    r = rates_table(df)
    assert set(r.condition_id) == {"baseline", "src_analyst", "src_all"}
    assert (r.f1_lo <= r.f1_rate).all() and (r.f1_rate <= r.f1_hi).all()
    o = order_table(df)
    assert o.iloc[0].test == "src_all_ratings_position" and o.iloc[0].linear_slope_pp > 0
