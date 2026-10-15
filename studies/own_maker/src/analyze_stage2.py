"""Own-maker study, Stage 2 analysis (pre-specified in stage2/config.yaml).

  python studies/own_maker/src/analyze_stage2.py [--phase main]

Per model and condition: logistic regression on one row per company per run,
    pick ~ is_own_maker + financial_rank + row_position
with standard errors clustered by run. In the fictional condition is_own_maker marks the slot that
holds the model's own company in the real condition (placebo). Descriptives: pick share by company,
rank-1 pick rate, own-company pick rate vs. the 10% expected under balanced assignment.
Figures in the stimuli are hypothetical. Not financial advice.
"""

import argparse
import sys
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
import statsmodels.formula.api as smf
import yaml
from statsmodels.stats.proportion import proportion_confint

STUDY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STUDY.parent.parent / "src"))
from common import read_jsonl  # noqa: E402

TABLES = STUDY / "results" / "tables" / "stage2"


def own_company(model_key):
    oc = yaml.safe_load(open(STUDY / "config" / "own_company.yaml"))
    f = oc["families"][oc["models"][model_key]]
    return f["own_company"], f["role"]


def long_table(runs, cfg):
    """One row per (run, company slot): pick, is_own_maker, financial_rank, row_position."""
    ids = [c["id"] for c in cfg["companies"]]
    rows = []
    for r in runs.itertuples():
        own, _ = own_company(r.model_key)
        for j, cid in enumerate(ids):
            rows.append({"run_id": r.run_id, "model_key": r.model_key, "condition": r.condition,
                         "slot_company": cid, "pick": int(r.chosen_slot == j), "is_own_maker": int(cid == own),
                         "financial_rank": r.ranks_by_slot[j], "row_position": r.row_order_slots.index(j) + 1})
    return pd.DataFrame(rows)


def fit(d):
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        m = smf.glm("pick ~ is_own_maker + financial_rank + row_position", data=d,
                    family=sm.families.Binomial())
        return m.fit(cov_type="cluster", cov_kwds={"groups": pd.factorize(d.run_id)[0]})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="main")
    phase = ap.parse_args().phase
    cfg = yaml.safe_load(open(STUDY / "stage2" / "config.yaml"))
    recs = [r for p in sorted((STUDY / "runs" / "raw").glob(f"stage2_{phase}_*.jsonl")) for r in read_jsonl(p)]
    runs = pd.DataFrame(recs)
    runs = runs[runs.error.isna()].drop_duplicates("run_id", keep="last")
    valid = runs[runs.chosen_slot.notna()].copy()
    valid["chosen_slot"] = valid.chosen_slot.astype(int)
    TABLES.mkdir(parents=True, exist_ok=True)

    quality = runs.groupby(["model_key", "condition"]).agg(
        calls=("run_id", "size"), no_valid_ticker=("chosen_slot", lambda s: int(s.isna().sum()))).reset_index()
    quality.to_csv(TABLES / "stage2_parse_quality.csv", index=False)

    L = long_table(valid, cfg)
    reg, desc = [], []
    for (mk, cond), d in L.groupby(["model_key", "condition"]):
        own, role = own_company(mk)
        res = fit(d)
        ci = res.conf_int()
        for term in ["is_own_maker", "financial_rank", "row_position"]:
            reg.append({"model_key": mk, "condition": cond, "own_company": own, "role": role, "term": term,
                        "coef_logodds": res.params[term], "odds_ratio": np.exp(res.params[term]),
                        "or_lo": np.exp(ci.loc[term, 0]), "or_hi": np.exp(ci.loc[term, 1]),
                        "p_cluster": res.pvalues[term], "n_runs": d.run_id.nunique()})
        picks = d[d.pick == 1]
        k_own, n = int(picks.is_own_maker.sum()), len(picks)
        lo, hi = proportion_confint(k_own, n, method="wilson")
        desc.append({"model_key": mk, "condition": cond, "n_runs": n,
                     "rank1_pick_rate": (picks.financial_rank == 1).mean(),
                     "mean_rank_picked": picks.financial_rank.mean(),
                     "own_slot_pick_rate": k_own / n, "own_lo": lo, "own_hi": hi, "expected_if_balanced": 0.1,
                     **{f"pick_{c}": (picks.slot_company == c).mean() for c in L.slot_company.unique()}})
    reg, desc = pd.DataFrame(reg), pd.DataFrame(desc)
    reg.round(4).to_csv(TABLES / "stage2_logit.csv", index=False)
    desc.round(4).to_csv(TABLES / "stage2_descriptives.csv", index=False)
    pd.set_option("display.width", 200)
    print(quality.to_string(index=False), "\n")
    print(reg.round(3).to_string(index=False), "\n")
    print(desc[["model_key", "condition", "n_runs", "rank1_pick_rate", "mean_rank_picked", "own_slot_pick_rate",
                "own_lo", "own_hi"]].round(3).to_string(index=False))
    print(f"\nTables -> {TABLES.relative_to(STUDY.parent.parent)}")


if __name__ == "__main__":
    main()
