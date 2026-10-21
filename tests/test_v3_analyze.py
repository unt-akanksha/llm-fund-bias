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
    ok, out, unreviewed = an.analyze("synthetic", log=log, out=tmp_path / "synthetic")
    assert ok and unreviewed == []
    t = pd.read_csv(out / "tests.csv").set_index(["family", "hypothesis"])
    for fam in prompts.FAMILIES:
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


def test_gate_stops_on_missing_call_and_refuses_overwrite(tmp_path, monkeypatch):
    monkeypatch.setattr(an, "OUTROOT", tmp_path)
    log = tmp_path / "log.jsonl"
    _synthetic_log(log)
    log.write_text("".join(open(log).readlines()[1:]))
    ok, out, _ = an.analyze("synthetic", log=log, out=tmp_path / "m")
    assert not ok and not (out / "tests.csv").exists()
    with pytest.raises(SystemExit):
        an.analyze("synthetic", log=log, out=tmp_path / "m")
    with pytest.raises(ValueError):
        an.safe_out(an.ROOT / "results" / "v2_analysis" / "x")
