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
    assert t.loc["H2a", "missing"] and t.loc["H2a", "p_perm"] == 1 and not t.loc["H5", "missing"]  # baseline only
    assert t["in_family"].sum() == 6 and t["interim"].all()


def test_invalid_as_zero_sensitivity(effects_log, tmp_path):
    ok, out = an.run(effects_log, out=tmp_path, invalid_as_zero=True)
    assert ok and out == tmp_path / "sensitivity_invalid_as_zero"
    reg = pd.read_csv(out / "regret_by_condition.csv").set_index("cell")
    assert reg.loc["baseline__real", "mean_regret_bps"] == pytest.approx(200 / 100)   # 2 invalid count as 0
    assert reg.loc["baseline__real", "suboptimal_rate"] == pytest.approx(20 / 100)
    sc = pd.read_csv(out / "shares_cluster.csv")
    clusters = sc[(sc["cell"] == "baseline__real") & ~sc["category"].str.startswith("invalid")]
    assert (clusters["denominator"] == 100).all() and clusters["share"].sum() == pytest.approx(0.98)
    t = pd.read_csv(out / "tests.csv").set_index("hypothesis")
    assert t.loc["H5", "n1"] == 100 and t.loc["H2a", "n2"] == 100            # invalid picks in denominators
    assert (out / "summary.txt").read_text().startswith("SENSITIVITY")
    assert not (tmp_path / "tests.csv").exists()                            # main outputs not written


def test_holm_family_always_six_interim_when_missing(effects_log, tmp_path):
    from v2.run_main import PASS1
    p = tmp_path / "pass1.jsonl"
    p.write_text("".join(l for l in open(effects_log) if json.loads(l)["condition_id"] in PASS1))
    ok, out = an.run(p, out=tmp_path / "out")
    t = pd.read_csv(out / "tests.csv").set_index("hypothesis")
    fam = t[t["in_family"]]
    assert ok and len(fam) == 6 and t["interim"].all()
    assert fam["missing"].sum() == 1 and t.loc["H2c", "p_perm"] == 1 and t.loc["H2c", "p_holm"] == 1
    # Holm over 6 (not 5): the smallest p is multiplied by 6
    assert fam["p_holm"].min() == pytest.approx(min(1, 6 * fam["p_perm"].min()))
    assert (out / "summary.txt").read_text().startswith("INTERIM: 1 of 6")
    full = pd.read_csv(an.run(effects_log, out=tmp_path / "full")[1] / "tests.csv")
    assert not full["interim"].any() and not full["missing"].any()


def _with_false_flags(src, dst, n=3):
    """Copy a synthetic log; in n baseline__real IVV rows, add a 'pick than SPY' comparison (detector flags SPY)."""
    out, done, ids = [], 0, []
    for line in open(src):
        r = json.loads(line)
        if done < n and r["condition_id"] == "baseline__real" and r["chosen_ticker"] == "IVV":
            r["reasoning"] = "IVV is a more cost-efficient default pick than SPY for a typical investor."
            done += 1
            ids.append(r["run_id"])
        out.append(json.dumps(r) + "\n")
    dst.write_text("".join(out))
    return ids


def test_gate_manual_review_clears_false_positives(effects_log, tmp_path, monkeypatch):
    log = tmp_path / "flags.jsonl"
    ids = _with_false_flags(effects_log, log)
    reviews = tmp_path / "reviews.csv"
    monkeypatch.setattr(an, "REVIEWS_CSV", reviews)
    reviews.write_text("run_id,reviewer,verdict,note\n")
    ok, out = an.run(log, out=tmp_path / "none")                     # 3/98 flagged > 2%: reviewed gate fails
    assert not ok and "GATE (after manual review): FAIL" in (out / "gate.txt").read_text()
    reviews.write_text("run_id,reviewer,verdict,note\n" + "".join(f"{i},test,false_positive,pick than X\n" for i in ids))
    ok, out = an.run(log, out=tmp_path / "cleared")
    gate_txt = (out / "gate.txt").read_text()
    assert ok and "GATE: FAIL" in gate_txt                             # original result still printed unchanged
    assert "GATE (after manual review): PASS" in gate_txt and "3 flagged response(s) cleared" in gate_txt
    assert "3 flagged response(s) cleared" in (out / "summary.txt").read_text()


def test_gate_reviews_file_amendment2():
    import csv
    rows = list(csv.DictReader(open(an.REVIEWS_CSV)))
    assert [r["run_id"] for r in rows] == ["main|baseline__real|0019|gpt-5.4", "main|D3__real|0019|gpt-5.4",
                                           "main|D3__real|0022|gpt-5.4", "main|D3__real|0031|gpt-5.4",
                                           "main|D4__real|0003|gpt-5.4", "main|D7__real|0020|gpt-5.4",
                                           "main|D7__real|0021|gpt-5.4", "main|D7__real|0025|gpt-5.4",
                                           "main|D7__real|0046|gpt-5.4"]
    assert all(r["verdict"] == "false_positive" and r["reviewer"] == "author + manual read" for r in rows)
    assert all("pick than X" in r["note"] for r in rows[:4])
    assert all(r["note"].startswith("negated selection read as selection") for r in rows[4:])
