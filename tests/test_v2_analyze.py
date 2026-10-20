"""Study 1 v2 analysis pipeline: tested ONLY on synthetic logs (known effects) and the pilot logs."""

import json

import pandas as pd
import pytest

from v2 import analyze as an, synth_logs as sl


@pytest.fixture(autouse=True)
def fewer_resamples(monkeypatch):
    monkeypatch.setattr(an, "N_PERM", 2000)
    monkeypatch.setattr(an, "N_BOOT", 2000)


@pytest.fixture(scope="module")
def effects_log(tmp_path_factory):
    p = tmp_path_factory.mktemp("syn") / "effects.jsonl"
    sl.make(p)
    return p


def test_guard_refuses_main_logs(tmp_path):
    with pytest.raises(an.GuardError):
        an.guard(an.ROOT / "runs" / "raw_v2" / "main_anything.jsonl", confirm_final=False)
    copy = tmp_path / "copied.jsonl"
    copy.write_text(json.dumps({"phase": "main", "condition_id": "baseline__real"}) + "\n")
    with pytest.raises(an.GuardError):
        an.guard(copy, confirm_final=False)
    an.guard(copy, confirm_final=True)          # explicit confirmation passes


def test_synthetic_known_effects(effects_log, tmp_path):
    ok, out = an.run(effects_log, out=tmp_path)
    assert ok
    reg = pd.read_csv(out / "regret_by_condition.csv").set_index("cell")
    for cell, expected in sl.EXPECTED_MEAN_REGRET.items():
        assert reg.loc[cell, "mean_regret_bps"] == pytest.approx(expected)
    assert reg.loc["baseline__real", "n_invalid"] == 2 and reg.loc["baseline__real", "n_valid"] == 98
    assert reg.loc["D3__real", "suboptimal_rate"] == pytest.approx(0.5)      # SPY regret 12 > 2
    assert reg.loc["D1__real", "suboptimal_rate"] == 0                        # VOO regret 2 = tie, not suboptimal
    tests = pd.read_csv(out / "tests.csv")
    fam = tests[tests["in_family"]]
    assert set(fam["hypothesis"]) == {"H2a", "H2b", "H2c", "H3", "H4", "H5"}
    assert fam["reject_holm_0.05"].all()
    sc = pd.read_csv(out / "shares_cluster.csv")
    inv = sc[(sc["cell"] == "baseline__real") & sc["category"].str.startswith("invalid")].iloc[0]
    assert inv["n"] == 2 and inv["share"] == pytest.approx(0.02)
    valid_shares = sc[(sc["cell"] == "baseline__real") & ~sc["category"].str.startswith("invalid")]["share"]
    assert valid_shares.sum() == pytest.approx(1.0)
    codes = pd.read_csv(out / "reasoning_codes.csv").set_index(["cell", "code"])
    assert codes.loc[("D1__real", "cites_cost"), "rate"] == 1.0
    assert (out / "summary.txt").exists() and (out / "sample_20.txt").exists()


def test_synthetic_null_rejects_nothing(tmp_path):
    p = tmp_path / "null.jsonl"
    sl.make(p, null=True)
    ok, out = an.run(p, out=tmp_path / "out")
    fam = pd.read_csv(out / "tests.csv").query("in_family")
    assert ok and len(fam) == 6 and not fam["reject_holm_0.05"].any()


def test_gate_stops_on_missing_call(effects_log, tmp_path):
    p = tmp_path / "short.jsonl"
    p.write_text("".join(open(effects_log).readlines()[1:]))
    ok, out = an.run(p, out=tmp_path / "out")
    assert not ok and not (out / "tests.csv").exists()


@pytest.mark.parametrize("model", ["llama3.1-8b", "qwen2.5-7b"])
def test_pilot_logs(model, tmp_path):
    ok, out = an.run(an.ROOT / "runs" / "raw_v2" / f"pilot_{model}.jsonl", out=tmp_path)
    assert ok
    t = pd.read_csv(out / "tests.csv").set_index("hypothesis")
    assert not t.loc["H2a", "in_family"] and t.loc["H5", "in_family"]     # pilot has baseline cells only
