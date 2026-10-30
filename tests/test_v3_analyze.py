"""Study 1 v3 analysis: tested on a synthetic log with known effects only. NOT DATA."""

import json
import random

import pandas as pd
import pytest

from v3 import analyze as an, prompts


def _synthetic_log(path, biased_costlier=40, base_costlier=5, fid_cut=20):
    """Per cell of 50: costlier picks = base_costlier at baseline/D1, biased_costlier under D3/D5/D7 (minus
    fid_cut under the fiduciary prompt); other picks go to the best fund. Reasoning names the chosen fund."""
    rows = []
    for cid, c in prompts.load_conditions().items():
        fam = prompts.FAMILIES[c["family"]]
        k = biased_costlier - (fid_cut if c["system"] == "fiduciary" else 0) if c["context"] in an.BIASED else \
            (0 if c["context"] == "D1" else base_costlier)
        picks = [fam["worst"]] * k + [fam["best"]] * (50 - k)
        random.Random(cid).shuffle(picks)
        for i, t in enumerate(picks):
            rows.append({"run_id": f"main|{cid}|{i:04d}|synthetic", "condition_id": cid, "family": c["family"],
                         "context": c["context"], "template": c["template"], "system": c["system"],
                         "model_key": "synthetic", "run_index": i, "error": None, "chosen_ticker": t,
                         "valid_pick": True, "hit_output_cap": False, "reasoning": f"I chose {t} for a typical investor.",
                         "raw_response": json.dumps({"reasoning": "x", "ticker": t})})
    path.write_text("".join(json.dumps(r) + "\n" for r in rows))


def test_known_effects(tmp_path, monkeypatch):
    monkeypatch.setattr(an, "OUTROOT", tmp_path)
    log = tmp_path / "log.jsonl"
    _synthetic_log(log)
    ok, out, unreviewed = an.analyze("synthetic", log=log, out=tmp_path / "synthetic", runs=50)
    assert ok and unreviewed == []
    t = pd.read_csv(out / "tests.csv").set_index(["family", "hypothesis"])
    assert set(t.index.get_level_values(0)) == set(prompts.ORIGINAL_FAMILIES)       # default: submitted families
    for fam in prompts.ORIGINAL_FAMILIES:
        h2 = t.loc[(fam, "H2 (D5)")]
        assert h2["estimate"] == pytest.approx((30 / 50) - (5 / 50)) and h2["reject_holm_0.05"]
        assert t.loc[(fam, "H3 (D1)"), "estimate"] == pytest.approx(-0.1)
        assert t.loc[(fam, "HF (fiduciary)"), "estimate"] == pytest.approx(-0.4) and t.loc[(fam, "HF (fiduciary)"), "reject_holm_0.05"]
        assert bool(t.loc[(fam, "HT (D3)"), "same_sign"])
    pooled = pd.read_csv(out / "pooled.csv")
    sp = pooled[(pooled.family == "sp500") & (pooled.context == "D7") & (pooled.system == "pooled") & (pooled.template == "pooled")].iloc[0]
    assert sp["costlier_share"] == pytest.approx(0.6) and sp["mean_regret_bps"] == pytest.approx(0.6 * 12)
    nd = pooled[(pooled.family == "ndx") & (pooled.context == "D7") & (pooled.system == "pooled") & (pooled.template == "pooled")].iloc[0]
    assert nd["mean_regret_bps"] == pytest.approx(0.6 * 7) and nd["mean_regret_er_only_bps"] == pytest.approx(0.6 * 3)


def test_new_families_amendment_v3_3(tmp_path, monkeypatch):
    """--families all: four families analyzed; regret per costlier pick is 172 bp (Dow 30) and 15 bp (Russell
    2000); a results folder other than results/v3_analysis/ is used by default."""
    monkeypatch.setattr(an, "OUTROOT", tmp_path / "v3")
    monkeypatch.setattr(an, "OUTROOT_EXT", tmp_path / "v3_1")
    log = tmp_path / "log.jsonl"
    _synthetic_log(log)
    fams = an.resolve_families("all")
    assert fams == ["sp500", "ndx", "dow30", "russell2000"] and an.resolve_families("ext") == ["dow30", "russell2000"]
    ok, out, _ = an.analyze("synthetic", log=log, runs=50, families=fams)
    assert ok and out == (tmp_path / "v3_1" / "synthetic").resolve()
    pooled = pd.read_csv(out / "pooled.csv")
    q = pooled[(pooled.context == "D7") & (pooled.system == "pooled") & (pooled.template == "pooled")].set_index("family")
    assert q.loc["dow30", "mean_regret_bps"] == pytest.approx(0.6 * 172)
    assert q.loc["russell2000", "mean_regret_bps"] == pytest.approx(0.6 * 15)
    assert q.loc["dow30", "mean_regret_er_only_bps"] == pytest.approx(0.6 * 172)   # net-cost regret outside Nasdaq
    t = pd.read_csv(out / "tests.csv")
    assert set(t["family"]) == set(fams)
    ok, out2, _ = an.analyze("synthetic", log=log, out=tmp_path / "v3_1" / "dow", runs=50, families=["dow30"])
    assert ok and set(pd.read_csv(out2 / "cells.csv")["family"]) == {"dow30"}


def test_gate_stops_on_missing_call_and_refuses_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(an, "OUTROOT", tmp_path)
    log = tmp_path / "log.jsonl"
    _synthetic_log(log)
    log.write_text("".join(open(log).readlines()[1:]))
    ok, out, _ = an.analyze("synthetic", log=log, out=tmp_path / "m", runs=50)
    assert not ok and not (out / "tests.csv").exists()
    with pytest.raises(SystemExit):
        an.analyze("synthetic", log=log, out=tmp_path / "m", runs=50)
    with pytest.raises(ValueError):
        an.safe_out(an.ROOT / "results" / "v2_analysis" / "x")


def test_runs_subset_uses_only_first_runs(tmp_path, monkeypatch):
    monkeypatch.setattr(an, "OUTROOT", tmp_path)
    log = tmp_path / "log.jsonl"
    _synthetic_log(log)
    ok, out, _ = an.analyze("synthetic", log=log, out=tmp_path / "m30", runs=30)
    cells = pd.read_csv(out / "cells.csv")
    assert ok and (cells["n_completed"] == 30).all()
    assert "runs per cell analyzed: 30" in (out / "summary.txt").read_text()


def test_planned_runs_by_vendor():
    assert an.planned_runs("gpt-5.4") == 30 and an.planned_runs("claude-opus-5.5") == 30
    assert an.planned_runs("qwen2.5-14b") == 50


def test_report_figures_and_summary(tmp_path, monkeypatch):
    from v3 import report
    monkeypatch.setattr(an, "OUTROOT", tmp_path)
    cfg = {"fake-small": {"provider": "openai", "size": "small"}, "fake-large": {"provider": "openai", "size": "large"}}
    for mk, k in [("fake-small", 40), ("fake-large", 0)]:
        log = tmp_path / f"{mk}.jsonl"
        _synthetic_log(log, biased_costlier=k, fid_cut=0)
        text = open(log).read().replace("|synthetic\"", f"|{mk}\"").replace("\"synthetic\"", f"\"{mk}\"")
        log.write_text(text)
        ok, _, _ = an.analyze(mk, log=log, out=tmp_path / mk, runs=50)
        assert ok
    df, skipped = report.collect(outroot=tmp_path, cfg=cfg)
    small = df[(df.model == "fake-small") & (df.family == "sp500")].iloc[0]
    assert small["share"] == pytest.approx(0.8) and skipped == []
    assert df[(df.model == "fake-large")]["share"].eq(0).all()
    paths, _ = report.figures(outroot=tmp_path, cfg=cfg)
    assert all(p.exists() and p.stat().st_size > 0 for p in paths)
    md = report.summary(outroot=tmp_path, cfg=cfg).read_text()
    assert "| fake-small | sp500 | 10% | 0% | 80% | 80% | 80% |" in md
    with pytest.raises(SystemExit):
        report.summary(outroot=tmp_path, cfg=cfg)


def test_gate_family_level_rule_amendment_v3_2(tmp_path, monkeypatch):
    """One real name-vs-ID mismatch in one cell (1/30 > 2%) passes at family level (1/1000), and is listed."""
    monkeypatch.setattr(an, "OUTROOT", tmp_path)
    monkeypatch.setattr(an, "REVIEWS", tmp_path / "reviews.csv")
    log = tmp_path / "log.jsonl"
    _synthetic_log(log)
    lines = open(log).readlines()
    r = json.loads(lines[0])
    other = [t for t in prompts.FAMILIES[r["family"]]["tickers"] if t != r["chosen_ticker"]][0]
    r["reasoning"] = f"I chose {other} for a typical investor."
    lines[0] = json.dumps(r) + "\n"
    log.write_text("".join(lines))
    ok, out, unreviewed = an.analyze("synthetic", log=log, out=tmp_path / "m", runs=50)
    assert ok and unreviewed == [r["run_id"]]
    assert "family" in (out / "gate.txt").read_text()
    (tmp_path / "reviews.csv").write_text(f"run_id,reviewer,verdict,note\n{r['run_id']},test,real_mismatch,x\n")
    ok, out, unreviewed = an.analyze("synthetic", log=log, out=tmp_path / "m2", runs=50)
    assert ok and unreviewed == [] and "1 reviewed and confirmed as real mismatches" in (out / "gate.txt").read_text()


def test_report_families_amendment_v3_3():
    from v3 import report
    fams, root, cfg = report.setup()
    assert fams == ["sp500", "ndx"] and root is None and not set(report.GPT6) & set(cfg)
    fams, root, cfg = report.setup("all")
    assert fams == ["sp500", "ndx", "russell2000", "dow30"] and root == an.OUTROOT_EXT
    assert set(report.GPT6) <= set(cfg) and report.line_of("gpt-6-sol", cfg["gpt-6-sol"]) == "openai-gpt6"
    assert report.costlier_note(fams) == ("Costlier fund = SPY (S&P 500), QQQ (Nasdaq-100), IWM (Russell 2000), "
                                          "RYDHX (Dow 30).")
