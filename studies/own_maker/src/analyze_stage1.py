"""Own-maker study, Stage 1 analysis: mention rates, own-maker lift, tests, top-10 per model.

  python studies/own_maker/src/analyze_stage1.py [--phase main]

Mention = the company is among the stocks suggested in a response (counted once per response).
Own-maker lift for model m with own company c:
    lift = rate_m(c) - mean over the OTHER-MAKER models m' of rate_m'(c)
(models of the same family/maker, e.g. two Qwen models, are excluded from each other's comparison)
so a company that every model names often (general popularity) gives no lift.
Tests per model: Wilson CI for each rate; 95% bootstrap CI for the lift (responses resampled within
each model); Fisher exact test (model m vs. the other models pooled); permutation test (model labels
shuffled among responses WITHIN each prompt variant). A joint permutation test sums the lifts of all
primary own-maker pairs. Secondary mappings (maker not listed) are reported but labeled secondary.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml
from scipy.stats import fisher_exact
from statsmodels.stats.proportion import proportion_confint

STUDY = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(STUDY.parent.parent / "src"))
from common import read_jsonl  # noqa: E402

import quality_checks  # noqa: E402


def gate(stage, phase, models, override):
    """Standing quality checks before any analysis; stop on failure unless explicitly overridden."""
    try:
        quality_checks.run(stage, phase, models)
    except quality_checks.GateFailure as e:
        if not override:
            sys.exit(f"STOP (quality gate): {e}\nRe-run with --override-gate '<reason>' only after review.")
        print(f"QUALITY GATE OVERRIDDEN ({override}): {e}")

import companies  # noqa: E402  (parser v2)
import companies_v1  # noqa: E402  (parser v1, frozen at own-maker-v0.1-frozen)

PARSERS = {"v1": companies_v1.companies_in, "v2": companies.companies_in}

TABLES = STUDY / "results" / "tables"
N_BOOT, N_PERM, SEED = 2000, 10000, 20261011


def load_runs(phase, parser="v2"):
    recs = [r for p in sorted((STUDY / "runs" / "raw").glob(f"stage1_{phase}_*.jsonl")) for r in read_jsonl(p)]
    df = pd.DataFrame(recs)
    df = df[df.error.isna()].drop_duplicates("run_id", keep="last").reset_index(drop=True)
    df["companies"] = df.raw_response.map(PARSERS[parser])
    return df


def load_json_failed(phase, ok_ids):
    """Final json_validate_failed calls (refusals/failures; gpt-oss), excluding run_ids later answered OK.
    Each gets an empty company list so it can be added back as a 'no stock named' response."""
    recs = [r for p in sorted((STUDY / "runs" / "raw").glob(f"stage1_{phase}_*.jsonl")) for r in read_jsonl(p)
            if "json_validate_failed" in (r.get("error") or "") and r["run_id"] not in ok_ids]
    df = pd.DataFrame(recs)
    if df.empty:
        return df
    df = df.drop_duplicates("run_id", keep="last").reset_index(drop=True)
    df["companies"] = [[] for _ in range(len(df))]
    return df


def refusal_table(ok, jf):
    """Refusal/failure rate per model x prompt (json_validate_failed among final calls), Wilson CI."""
    rows = []
    allc = pd.concat([ok.assign(refused=0), jf.assign(refused=1)])
    for (mk, pid), g in allc.groupby(["model_key", "prompt_id"]):
        k, n = int(g.refused.sum()), len(g)
        lo, hi = proportion_confint(k, n, method="wilson")
        rows.append({"model_key": mk, "prompt_id": pid, "final_calls": n, "refused": k, "refusal_rate": k / n,
                     "lo": lo, "hi": hi})
    return pd.DataFrame(rows)


def families():
    """model_key -> family (models without a family count as their own family)."""
    return yaml.safe_load(open(STUDY / "config" / "own_company.yaml"))["models"]


def other_maker_models(target, models):
    """Comparison set for a lift: models from a DIFFERENT family (maker) than the target."""
    fam = families()
    f = fam.get(target, target)
    return [m for m in models if m != target and fam.get(m, m) != f]


def own_pairs(models):
    """[(model_key, company_id, role)] from config/own_company.yaml, for models present in the data."""
    cfg = yaml.safe_load(open(STUDY / "config" / "own_company.yaml"))
    out = []
    for mk in models:
        fam = cfg["models"].get(mk)
        if fam is None:
            continue
        f = cfg["families"][fam]
        for c in (f["own_company"] if isinstance(f["own_company"], list) else [f["own_company"]]):
            out.append((mk, c, f["role"]))
    return out


def mention_matrix(df):
    """Boolean DataFrame: one row per response, one column per canonical company (ETF/UNKNOWN excluded)."""
    comps = sorted({c for cs in df.companies for c in cs if ":" not in c})
    return pd.DataFrame([{c: c in set(cs) for c in comps} for cs in df.companies], index=df.index)


def lift(m_col, models, target, others):
    """rate in target model minus mean rate in the other-maker models."""
    rates = m_col.groupby(models).mean()
    return rates[target] - rates[others].mean()


def permute_within(models, strata, rng):
    """Shuffle model labels among responses within each stratum (prompt variant)."""
    out = models.copy()
    for _, idx in models.groupby(strata).groups.items():
        out.loc[idx] = rng.permutation(models.loc[idx].values)
    return out


def lift_table(df, M, pairs):
    rng = np.random.default_rng(SEED)
    models = df.model_key
    rows, perm_stats, observed = [], [], []
    for mk, c, role in pairs:
        col = M[c] if c in M else pd.Series(False, index=df.index)
        g = col.groupby(models)
        k, n = g.sum(), g.count()
        others = other_maker_models(mk, list(k.index))
        obs = lift(col, models, mk, others)
        # bootstrap: resample responses within each model
        boots = []
        for _ in range(N_BOOT):
            r = {m: rng.choice(col[models == m].values, size=n[m], replace=True).mean() for m in k.index}
            boots.append(r[mk] - np.mean([r[o] for o in others]))
        k_o, n_o = int(k[others].sum()), int(n[others].sum())
        _, p_fisher = fisher_exact([[int(k[mk]), int(n[mk] - k[mk])], [k_o, n_o - k_o]])
        lo, hi = proportion_confint(int(k[mk]), int(n[mk]), method="wilson")
        rows.append({"model_key": mk, "own_company": c, "role": role, "n_model": int(n[mk]),
                     "own_rate": k[mk] / n[mk], "own_lo": lo, "own_hi": hi,
                     "others": ";".join(others),
                     "others_rate_mean": float(np.mean([k[o] / n[o] for o in others])),
                     "others_rates": ";".join(f"{o}={k[o] / n[o]:.3f}" for o in others),
                     "lift_pp": 100 * obs, "lift_lo_pp": 100 * np.percentile(boots, 2.5),
                     "lift_hi_pp": 100 * np.percentile(boots, 97.5), "p_fisher": p_fisher})
        observed.append((mk, c, role, obs, others))
    # permutation tests (same permutations for every pair, plus the joint statistic over primary pairs)
    null = np.zeros((N_PERM, len(observed)))
    for b in range(N_PERM):
        pm = permute_within(models, df.prompt_id, rng)
        for j, (mk, c, _, _, others) in enumerate(observed):
            col = M[c] if c in M else pd.Series(False, index=df.index)
            null[b, j] = lift(col, pm, mk, others)
    for j, (_, _, _, obs, _) in enumerate(observed):
        rows[j]["p_perm_two_sided"] = (np.sum(np.abs(null[:, j]) >= abs(obs) - 1e-12) + 1) / (N_PERM + 1)
        rows[j]["p_perm_one_sided"] = (np.sum(null[:, j] >= obs - 1e-12) + 1) / (N_PERM + 1)
    prim = [j for j, o in enumerate(observed) if o[2] == "primary"]
    joint = None
    if prim:
        s_obs = sum(observed[j][3] for j in prim)
        s_null = null[:, prim].sum(axis=1)
        joint = {"pairs": ";".join(f"{observed[j][0]}:{observed[j][1]}" for j in prim),
                 "sum_lift_pp": 100 * s_obs,
                 "p_perm_one_sided": (np.sum(s_null >= s_obs - 1e-12) + 1) / (N_PERM + 1),
                 "p_perm_two_sided": (np.sum(np.abs(s_null) >= abs(s_obs) - 1e-12) + 1) / (N_PERM + 1),
                 "n_perm": N_PERM}
    return pd.DataFrame(rows), joint


def rates_table(df, M):
    rows = []
    for mk, idx in df.groupby("model_key").groups.items():
        sub = M.loc[idx]
        for c in M.columns:
            k, n = int(sub[c].sum()), len(sub)
            if k == 0:
                continue
            lo, hi = proportion_confint(k, n, method="wilson")
            rows.append({"model_key": mk, "company": c, "k": k, "n": n, "rate": k / n, "lo": lo, "hi": hi})
    t = pd.DataFrame(rows).sort_values(["model_key", "rate"], ascending=[True, False])
    t["rank"] = t.groupby("model_key").rate.rank(ascending=False, method="min").astype(int)
    return t


def own_by_prompt(df, M, pairs):
    rows = []
    for mk, c, role in pairs:
        col = M[c] if c in M else pd.Series(False, index=df.index)
        for pid, g in df.groupby("prompt_id"):
            r = col.loc[g.index].groupby(g.model_key).mean()
            rows.append({"model_key": mk, "own_company": c, "role": role, "prompt_id": pid,
                         "own_rate": r.get(mk, np.nan), "others_rate_mean": r.drop(mk, errors="ignore").mean()})
    return pd.DataFrame(rows)


def parse_quality(df):
    rows = []
    for mk, g in df.groupby("model_key"):
        allc = [c for cs in g.companies for c in cs]
        rows.append({"model_key": mk, "responses": len(g),
                     "responses_with_0_parsed": int((g.companies.map(len) == 0).sum()),
                     "mean_entries": float(np.mean(g.companies.map(len))),
                     "share_unknown": np.mean([c.startswith("UNKNOWN:") for c in allc]) if allc else np.nan,
                     "share_etf": np.mean([c.startswith("ETF:") for c in allc]) if allc else np.nan,
                     "top_unknown": ";".join(pd.Series([c for c in allc if c.startswith("UNKNOWN:")])
                                             .value_counts().head(10).index)})
    return pd.DataFrame(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="main")
    ap.add_argument("--models", help="comma-separated model keys to include (default: all in the logs)")
    ap.add_argument("--out", help="subfolder of results/tables for this analysis (e.g. local)")
    ap.add_argument("--parser", choices=sorted(PARSERS), default="v2")
    ap.add_argument("--override-gate", metavar="REASON", help="continue despite a failed quality gate (reason is printed)")
    a = ap.parse_args()
    phase = a.phase
    gate("stage1", phase, a.models.split(",") if a.models else None, a.override_gate)
    df = load_runs(phase, a.parser)
    if a.models:
        df = df[df.model_key.isin(a.models.split(","))].reset_index(drop=True)
    jf = load_json_failed(phase, set(df.run_id))
    if a.models and not jf.empty:
        jf = jf[jf.model_key.isin(a.models.split(","))].reset_index(drop=True)
    M = mention_matrix(df)
    pairs = own_pairs(sorted(df.model_key.unique()))
    out = TABLES if phase == "main" else TABLES / phase
    out = out / a.out if a.out else out
    out.mkdir(parents=True, exist_ok=True)

    lifts, joint = lift_table(df, M, pairs)
    rates = rates_table(df, M)
    top10 = rates[rates["rank"] <= 10]
    lifts.round(4).to_csv(out / "stage1_lift.csv", index=False)
    pd.DataFrame([joint]).round(4).to_csv(out / "stage1_lift_joint.csv", index=False)
    rates.round(4).to_csv(out / "stage1_mention_rates.csv", index=False)
    top10.round(4).to_csv(out / "stage1_top10.csv", index=False)
    own_by_prompt(df, M, pairs).round(4).to_csv(out / "stage1_own_by_prompt.csv", index=False)
    parse_quality(df).round(4).to_csv(out / "stage1_parse_quality.csv", index=False)
    if not jf.empty:
        # main tables above EXCLUDE refusals from the denominator; sensitivity: include them as
        # responses that name no stock
        refusal_table(df, jf).round(4).to_csv(out / "stage1_refusals.csv", index=False)
        dfr = pd.concat([df, jf], ignore_index=True)
        Mr = mention_matrix(dfr)
        lr, jr = lift_table(dfr, Mr, pairs)
        lr.round(4).to_csv(out / "stage1_lift_with_refusals.csv", index=False)
        pd.DataFrame([jr]).round(4).to_csv(out / "stage1_lift_joint_with_refusals.csv", index=False)
        rates_table(dfr, Mr).round(4).to_csv(out / "stage1_mention_rates_with_refusals.csv", index=False)
        print(f"Refusals (json_validate_failed, final): {len(jf)}; see stage1_refusals.csv and *_with_refusals.csv")

    pd.set_option("display.width", 200)
    print(lifts.round(3).to_string(index=False))
    print("\nJoint (primary pairs):", joint)
    for mk, g in top10.groupby("model_key"):
        print(f"\nTop-10 {mk}: " + ", ".join(f"{r.company} {r.rate:.0%}" for r in g.itertuples()))
    print("\n" + parse_quality(df).to_string(index=False))
    print(f"\nTables -> {out.relative_to(STUDY.parent.parent)}")


if __name__ == "__main__":
    main()
