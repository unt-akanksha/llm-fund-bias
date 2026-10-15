"""Standing quality checks: name/ID gate, counts, samples, shares, Stage 2 balance, Groq finish reasons."""

import json

import pandas as pd
import pytest

import quality_checks as Q
import stage2_design as S2

CFG, PR = S2.load()


def s2_row(run_id, condition, reasoning, slot, i=0, provider="ollama", finish=None):
    ranks, rows = S2.plan(CFG, i)
    return {"run_id": run_id, "model_key": "m", "condition": condition, "provider": provider,
            "raw_response": json.dumps({"reasoning": reasoning, "ticker": "X"}), "chosen_slot": slot,
            "ranks_by_slot": [ranks[j] for j in range(10)], "row_order_slots": rows, "finish_reason": finish}


def test_stage2_name_vs_ticker_match_mismatch_and_gate():
    rows = [s2_row(f"r{i}", "real_names", "Meta Platforms offers the best growth and margins.", 0) for i in range(48)]
    rows += [s2_row("x1", "real_names", "Microsoft stands out with the strongest financials.", 0),   # mismatch
             s2_row("x2", "real_names", "The figures favor a diversified pick.", 0)]                # unclassifiable
    rows += [s2_row(f"f{i}", "fictional_names", "Norvane Systems (NRVQ) leads on every metric.", 0) for i in range(5)]
    t = Q.stage2_name_id(pd.DataFrame(rows), CFG).set_index("condition")
    assert t.loc["real_names", "n_mismatch"] == 1 and t.loc["real_names", "n_classifiable"] == 49
    assert t.loc["real_names", "over_threshold"]                  # 1/49 = 2.04% > 2%
    assert t.loc["fictional_names", "n_mismatch"] == 0 and not t.loc["fictional_names", "over_threshold"]


def test_rejected_name_is_not_the_recommendation():
    r = s2_row("a", "real_names", "While Microsoft is solid, Alphabet has the strongest margins.", 3)
    assert Q.stage2_name_id(pd.DataFrame([r]), CFG).n_mismatch.iloc[0] == 0


def test_counts_vs_planned_flags_missing_runs():
    df = pd.DataFrame({"model_key": ["m"] * 3, "condition": ["real_names", "real_names", "fictional_names"]})
    t = Q.counts_vs_planned(df, {("m", "real_names"): 2, ("m", "fictional_names"): 2}, "condition")
    assert t.set_index("condition").short.to_dict() == {"real_names": 0, "fictional_names": 1}


def test_sample_is_fixed_and_twenty():
    df = pd.DataFrame({"run_id": range(100), "raw_response": [str(i) for i in range(100)]})
    a, b = Q.sample_responses(df), Q.sample_responses(df)
    assert len(a) == 20 and a.run_id.tolist() == b.run_id.tolist()


def test_shares_sum_to_one_scalar_and_lists():
    df = pd.DataFrame({"g": [1, 1, 2], "c": ["A", "B", "A"], "l": [["A", "B"], ["C"], ["A"]]})
    assert Q.shares_sum_to_one(df, ["g"], "c") < 1e-12 and Q.shares_sum_to_one(df, ["g"], "l") < 1e-12


def test_stage2_balance_detects_imbalance():
    good = pd.DataFrame([s2_row(f"r{i}", "real_names", "", 0, i=i) for i in range(50)])
    assert Q.stage2_balance(good, CFG).balanced_companies.all()
    bad = good.copy()
    bad.at[0, "ranks_by_slot"] = bad.at[1, "ranks_by_slot"]    # duplicate one run's assignment
    assert not Q.stage2_balance(bad, CFG).balanced_companies.all()


def test_groq_finish_share():
    df = pd.DataFrame([s2_row("a", "real_names", "", 0, provider="groq", finish="stop"),
                       s2_row("b", "real_names", "", 0, provider="groq", finish="length"),
                       s2_row("c", "real_names", "", 0, provider="ollama")])
    t = Q.groq_finish(df)
    assert t.calls.iloc[0] == 2 and t.share_not_stop.iloc[0] == 0.5


def test_study1_gate_stops_over_two_percent(tmp_path):
    rows = [{"run_id": f"r{i}", "model_key": "m", "condition_id": "c", "chosen_fund": "F1",
             "reasoning_text": "The Alder US Index Fund has the lowest fee."} for i in range(97)]
    rows += [{"run_id": f"x{i}", "model_key": "m", "condition_id": "c", "chosen_fund": "F2",
              "reasoning_text": "The Alder US Index Fund has the lowest fee."} for i in range(3)]
    p = tmp_path / "clean.csv"
    pd.DataFrame(rows).to_csv(p, index=False)
    with pytest.raises(Q.GateFailure, match="3.0%"):
        Q.run("study1", clean=p, out=lambda *_: None)
