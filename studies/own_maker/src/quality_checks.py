"""Standing quality checks, run before any analysis of a new run set (read-only; changes no design file).

  python studies/own_maker/src/quality_checks.py --set stage1 [--phase main] [--models a,b]
  python studies/own_maker/src/quality_checks.py --set stage2 [--phase main]
  python studies/own_maker/src/quality_checks.py --set study1 --clean runs/clean.csv

Checks (each prints a table; the gate fails on the first two):
  1. name vs. ID: the item the reasoning recommends (study 1 rule-based detector, src/name_id_check.py)
     vs. the chosen ID. Study 1 style: fund name vs. fund ID. Stage 2: company named vs. chosen ticker.
     GATE: stop if any model x condition cell exceeds 2% mismatches.
  2. counts per condition vs. planned. GATE: stop if any cell is short of plan (missing runs).
  3. 20 random raw responses (fixed seed) to read, and choice shares summing to 1.
  4. Stage 2 only: best-financials (rank 1) assignment balanced across companies (exactly equal) and
     reported across row positions (chi-square; warning only, row position is a covariate).
  5. Groq runs: share of calls with finish_reason other than "stop".
Stage 1 has no single chosen ID, so check 1 does not apply to it.
"""

import argparse
import json
import random
import sys
from pathlib import Path

import pandas as pd
import yaml
from scipy.stats import chisquare

STUDY = Path(__file__).resolve().parent.parent
REPO = STUDY.parent.parent
sys.path.insert(0, str(REPO / "src"))
from common import read_jsonl  # noqa: E402
from name_id_check import name_map, recommended_fund  # noqa: E402  (study 1 detector, unchanged)

MISMATCH_MAX = 0.02
N_SAMPLE, SAMPLE_SEED = 20, 20261015


class GateFailure(Exception):
    pass


# ---------- loading ----------

def load_raw(stage, phase, models=None):
    recs = [r for p in sorted((STUDY / "runs" / "raw").glob(f"{stage}_{phase}_*.jsonl")) for r in read_jsonl(p)]
    df = pd.DataFrame(recs)
    if df.empty:
        raise SystemExit(f"No {stage} logs for phase '{phase}'.")
    if models:
        df = df[df.model_key.isin(models)]
    ok = df[df.error.isna()].drop_duplicates("run_id", keep="last")
    # final json_validate_failed calls (refusals; not re-asked) count as completed, reported separately
    jf = df[df.error.fillna("").str.contains("json_validate_failed") & ~df.run_id.isin(ok.run_id)]
    return ok.reset_index(drop=True), jf.drop_duplicates("run_id", keep="last").reset_index(drop=True)


def reasoning_of(raw):
    try:
        return str(json.loads(raw).get("reasoning", ""))
    except (json.JSONDecodeError, TypeError, AttributeError):
        return raw or ""


# ---------- check 1: name vs ID ----------

def stage2_name_maps(cfg):
    """{word: slot} for real and fictional names: distinctive name words plus tickers."""
    real = {}
    extra = {"GOOGL": ["Google"], "JNJ": ["Johnson"], "PG": ["Procter", "P&G"], "NVDA": ["Nvidia"],
             "JPM": ["JPMorgan"], "META": ["Facebook"]}
    for j, c in enumerate(cfg["companies"]):
        for w in [c["name"].split()[0], c["ticker"], *extra.get(c["id"], [])]:
            real[w] = j
    fict = {}
    for j, c in enumerate(cfg["fictional"]):
        fict[c["name"].split()[0]] = j
        fict[c["ticker"]] = j
    return {"real_names": real, "fictional_names": fict}


def mismatch_table(df, group_cols, chosen_col, rec_col):
    rows = []
    for key, g in df.groupby(group_cols):
        c = g[g[rec_col].notna() & g[chosen_col].notna()]
        k = int((c[rec_col] != c[chosen_col]).sum())
        rows.append({**dict(zip(group_cols, key if isinstance(key, tuple) else (key,))),
                     "n": len(g), "n_classifiable": len(c), "n_mismatch": k,
                     "mismatch_rate": k / len(c) if len(c) else 0.0,
                     "mismatched_run_ids": ";".join(c.loc[c[rec_col] != c[chosen_col], "run_id"])})
    t = pd.DataFrame(rows)
    t["over_threshold"] = t.mismatch_rate > MISMATCH_MAX
    return t


def stage2_name_id(df, cfg):
    maps = stage2_name_maps(cfg)
    df = df.copy()
    df["recommended_slot"] = [recommended_fund(reasoning_of(r.raw_response), maps[r.condition])[0]
                              for r in df.itertuples()]
    return mismatch_table(df, ["model_key", "condition"], "chosen_slot", "recommended_slot")


def study1_name_id(clean):
    names = name_map()
    clean = clean.copy()
    clean["recommended_fund"] = clean.reasoning_text.map(lambda t: recommended_fund(t, names)[0])
    return mismatch_table(clean, ["model_key", "condition_id"], "chosen_fund", "recommended_fund")


# ---------- check 2/3: counts, samples, shares ----------

def planned_counts(stage, df):
    if stage == "stage1":
        pr = yaml.safe_load(open(STUDY / "prompts" / "stage1_prompts.yaml"))["prompts"]
        n = yaml.safe_load(open(STUDY / "config" / "models.yaml"))["stage1_runs_per_prompt"]
        return {(mk, p): n for mk in df.model_key.unique() for p in pr}, "prompt_id"
    cfg = yaml.safe_load(open(STUDY / "stage2" / "config.yaml"))
    return ({(mk, c): cfg["runs_per_condition"] for mk in df.model_key.unique() for c in cfg["conditions"]},
            "condition")


def counts_vs_planned(df, planned, cond_col):
    got = df.groupby(["model_key", cond_col]).size()
    t = pd.DataFrame([{"model_key": mk, cond_col: c, "planned": n, "completed": int(got.get((mk, c), 0))}
                      for (mk, c), n in planned.items()])
    t["short"] = t.planned - t.completed
    return t


def sample_responses(df, n=N_SAMPLE, seed=SAMPLE_SEED):
    idx = sorted(random.Random(seed).sample(range(len(df)), min(n, len(df))))
    return df.iloc[idx][["run_id", "raw_response"]]


def shares_sum_to_one(df, group_cols, choice_col):
    """Max |sum of choice shares - 1| over groups (choice_col may hold lists: shares of all entries)."""
    worst = 0.0
    for _, g in df.groupby(group_cols):
        s = g[choice_col].explode() if g[choice_col].map(lambda v: isinstance(v, list)).any() else g[choice_col]
        s = s.dropna()
        if len(s):
            worst = max(worst, abs(s.value_counts(normalize=True).sum() - 1))
    return worst


# ---------- check 4: Stage 2 balance ----------

def stage2_balance(df, cfg):
    ids = [c["id"] for c in cfg["companies"]]
    rows, pos_rows = [], []
    for (mk, cond), g in df.groupby(["model_key", "condition"]):
        best = g.ranks_by_slot.map(lambda r: r.index(1))
        comp = best.map(lambda j: ids[j]).value_counts().reindex(ids, fill_value=0)
        pos = pd.Series([o.index(b) + 1 for o, b in zip(g.row_order_slots, best)]).value_counts().reindex(
            range(1, 11), fill_value=0)
        rows.append({"model_key": mk, "condition": cond, "n": len(g), "rank1_min_per_company": int(comp.min()),
                     "rank1_max_per_company": int(comp.max()), "balanced_companies": bool(comp.min() == comp.max()),
                     "rank1_by_row_position": ";".join(f"{p}:{k}" for p, k in pos.items()),
                     "p_chi2_rank1_position_uniform": chisquare(pos).pvalue})
    return pd.DataFrame(rows)


# ---------- check 5: Groq finish reasons ----------

def groq_finish(df):
    g = df[df.provider == "groq"]
    if g.empty:
        return pd.DataFrame()
    fr = g.get("finish_reason", pd.Series(index=g.index, dtype=object))
    return (g.assign(not_stop=(fr != "stop")).groupby("model_key")
            .agg(calls=("run_id", "size"), not_stop=("not_stop", "sum")).assign(
                share_not_stop=lambda t: t.not_stop / t.calls).reset_index())


# ---------- driver ----------

def run(stage, phase="main", models=None, clean=None, out=print):
    """Run all applicable checks; print them; raise GateFailure on a failed gate."""
    failures = []
    if stage == "study1":
        df = pd.read_csv(clean)
        ni = study1_name_id(df)
        out("1. Name vs. ID (fund named in reasoning vs. fund ID):\n" + ni.drop(columns="mismatched_run_ids")
            .round(3).to_string(index=False))
        out(f"3. Choice shares sum to 1 (max deviation {shares_sum_to_one(df, ['model_key', 'condition_id'], 'chosen_fund'):.1e})")
        if ni.over_threshold.any():
            failures.append(f"name/ID mismatch > {MISMATCH_MAX:.0%} in: " + ", ".join(
                f"{r.model_key}/{r.condition_id} ({r.mismatch_rate:.1%})" for r in ni[ni.over_threshold].itertuples()))
    else:
        tag = "stage1" if stage == "stage1" else "stage2"
        df, jf = load_raw(tag, phase, models)
        planned, cond_col = planned_counts(tag, df)
        cnt = counts_vs_planned(pd.concat([df, jf]), planned, cond_col)
        out("2. Completed vs. planned runs (completed includes final json_validate_failed refusals):\n"
            + cnt.groupby("model_key")[["planned", "completed", "short"]].sum().to_string())
        if not jf.empty:
            out("   json_validate_failed (refusals, final): " + ", ".join(
                f"{mk} {n}" for mk, n in jf.groupby("model_key").size().items()))
        if (cnt.short > 0).any():
            failures.append("missing runs in: " + ", ".join(
                f"{r.model_key}/{getattr(r, cond_col)} ({r.short})" for r in cnt[cnt.short > 0].itertuples()))
        out(f"3. {N_SAMPLE} random raw responses (seed {SAMPLE_SEED}):")
        for r in sample_responses(df).itertuples():
            out(f"--- {r.run_id}\n{r.raw_response}")
        if tag == "stage1":
            sys.path.insert(0, str(STUDY / "src"))
            from companies import companies_in
            df["companies"] = df.raw_response.map(companies_in)
            out(f"3. Entry shares sum to 1 (max deviation {shares_sum_to_one(df, ['model_key', 'prompt_id'], 'companies'):.1e})")
        else:
            cfg = yaml.safe_load(open(STUDY / "stage2" / "config.yaml"))
            out(f"3. Choice shares sum to 1 (max deviation {shares_sum_to_one(df, ['model_key', 'condition'], 'chosen_slot'):.1e})")
            ni = stage2_name_id(df, cfg)
            out("1/2. Company named in reasoning vs. chosen ticker:\n" + ni.drop(columns="mismatched_run_ids")
                .round(3).to_string(index=False))
            if ni.over_threshold.any():
                failures.append(f"name/ticker mismatch > {MISMATCH_MAX:.0%} in: " + ", ".join(
                    f"{r.model_key}/{r.condition} ({r.mismatch_rate:.1%})" for r in ni[ni.over_threshold].itertuples()))
            bal = stage2_balance(df, cfg)
            out("4. Best-financials balance:\n" + bal.round(3).to_string(index=False))
            if not bal.balanced_companies.all():
                out("   WARNING: rank-1 profile not equally spread over companies (incomplete blocks?)")
            if (bal.p_chi2_rank1_position_uniform < 0.05).any():
                out("   WARNING: rank-1 row positions depart from uniform (row position is a regression covariate)")
        gf = groq_finish(df)
        if not gf.empty:
            out("5. Groq finish_reason other than 'stop':\n" + gf.round(4).to_string(index=False))
    if failures:
        raise GateFailure("; ".join(failures))
    out("Quality gate: PASS")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", required=True, choices=["stage1", "stage2", "study1"])
    ap.add_argument("--phase", default="main")
    ap.add_argument("--models")
    ap.add_argument("--clean", default=str(REPO / "runs" / "clean.csv"))
    a = ap.parse_args()
    try:
        run(a.set, a.phase, a.models.split(",") if a.models else None, a.clean)
    except GateFailure as e:
        sys.exit(f"STOP (quality gate): {e}")


if __name__ == "__main__":
    main()
