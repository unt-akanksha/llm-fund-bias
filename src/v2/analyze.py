"""Study 1 v2 analysis pipeline (design_v2.md §3, §8; Amendment 1). One JSONL log, one model per run.

  python src/v2/analyze.py LOG --model MODEL_KEY [--out DIR] [--expected-runs N] [--confirm-final]

Refuses the main-run logs (runs/raw_v2/main_*.jsonl, or any log whose rows are phase "main") unless
--confirm-final is passed. Develop and test only on the pilot logs and on synthetic logs
(src/v2/synth_logs.py).

Steps:
  1. Quality gate (§8). Stops on failure: planned != completed per cell, name-vs-ID mismatch > 2% per cell,
     output-cap / cut-off > 2% per cell. Invalid tickers are a flagged outcome (Amendment 1). Writes
     gate.txt and sample_20.txt (20 random raw responses, fixed seed).
  2. Tables (CSV): shares_cluster.csv (incl. "invalid" as its own category), shares_fund.csv,
     regret_by_condition.csv (≤ 2 bp tie rule), tests.csv (H1 estimates; H2a/b/c, H3, H4, H5 with CIs,
     raw and Holm p in one family), reasoning_codes.csv, cost_codes_vs_regret.csv.
  3. summary.txt: one page.
  --invalid-as-zero: sensitivity (own folder): invalid picks count as non-target picks with regret 0 in all
     share, regret and test denominators. Main outputs are unchanged.
  The Holm family always has 6 tests (H2a, H2b, H2c, H3, H4, H5); a test whose cells are missing from the log
  counts with p = 1 and the output is stamped INTERIM (summary.txt, tests.csv column "interim").

Choices this code makes where §8 is silent (also printed in summary.txt):
  - Invalid picks (off-table or typo) are their own category: reported with their rate, and excluded from
    the denominators of cluster/fund shares, regret and the tests (author's decision, 2026-10-20).
  - The Holm family uses the permutation p (two-group: difference in mean regret; H4: one-way F; H5:
    chi-square on the per-fund pick distribution). OLS with HC3 SEs and bootstrap 95% CIs are reported
    next to it.
  - H5 outcome: the per-fund pick distribution, real vs. name-masked baseline (the "name prior" moves
    picks, §6). The difference in mean regret is reported as a secondary row outside the family.
  - Regret is computed for every valid pick; funds with no same-index peer have regret 0 by definition.
"""

import argparse
import csv
import fnmatch
import json
import random
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import pandas as pd
import statsmodels.api as sm
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import proportion_confint

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from name_id_check import recommended_fund  # noqa: E402

from v2 import cost, reasoning_codes as rc, render  # noqa: E402
from v2.run_main import name_map  # noqa: E402

MAIN_GLOB = str(ROOT / "runs" / "raw_v2" / "main_*.jsonl")
GATE_MAX = 0.02
ALPHA = 0.05
N_PERM = N_BOOT = 10_000
SEED = 20261020
CLUSTERS = ["sp500", "nasdaq100", "total_us", "us_agg_bond", "international"]
HYPOTHESES = [  # (id, cell, reference cell, direction) -- real names; one Holm family
    ("H2a", "D3__real", "baseline__real", "greater"),
    ("H2b", "D5__real", "baseline__real", "greater"),
    ("H2c", "D7__real", "baseline__real", "greater"),
    ("H3", "D1__real", "baseline__real", "less"),
]
FAMILY_SIZE = 6     # H2a, H2b, H2c, H3, H4, H5: fixed; a missing test counts with p = 1 (output "interim")
ORDER_CELLS = ["W1__real", "W2__real", "W3__real", "W4__real"]


class GuardError(Exception):
    pass


# ---------------- loading ----------------

def guard(path, confirm_final):
    p = str(Path(path).resolve())
    if fnmatch.fnmatch(p, MAIN_GLOB) and not confirm_final:
        raise GuardError(f"{path} is a main-run log; pass --confirm-final to analyze it")
    if not confirm_final:
        with open(path) as f:
            for line in f:
                if line.strip() and json.loads(line).get("phase") == "main":
                    raise GuardError(f"{path} contains main-run rows; pass --confirm-final to analyze it")


def funds_table():
    funds = render.load_funds(render.FILLED_CSV, placeholder=False)
    return funds, {f["ticker"]: f for f in funds}


def load_log(path, model, funds):
    """-> one row per planned call (deduplicated by run_id; a later successful retry wins)."""
    tickers = [f["ticker"] for f in funds]
    code_to_ticker = {code: t for t, (code, _) in render.mask_map(tickers).items()}
    rows = [json.loads(line) for line in open(path) if line.strip()]
    models = sorted({r.get("model_key") for r in rows})
    if model is None:
        if len(models) != 1:
            raise ValueError(f"log has models {models}; pass --model")
        model = models[0]
    out = {}
    for r in rows:
        if r.get("model_key") != model or r.get("kind") == "probe":
            continue
        rid = r.get("run_id") or f"{r['condition_id']}|{r['run_index']}"
        ok = not r.get("error")
        if "chosen_ticker" in r:
            chosen = r["chosen_ticker"]
        else:                                   # pilot schema: raw ticker, masked codes not yet mapped
            raw = r.get("chosen_ticker_raw")
            chosen = code_to_ticker.get(raw) if r.get("naming") == "masked" else raw
        cut = r["hit_output_cap"] if "hit_output_cap" in r else bool((r.get("tokens_out") or 0) >= 300)
        rec = {"run_id": rid, "condition_id": r["condition_id"], "cell": r["condition_id"].removeprefix("pilot_"),
               "naming": r.get("naming"), "run_index": r.get("run_index"), "completed": ok,
               "chosen": chosen if ok else None, "cutoff": bool(cut), "reasoning": r.get("reasoning"),
               "raw_response": r.get("raw_response")}
        if rid not in out or ok:
            out[rid] = rec
    df = pd.DataFrame(out.values())
    df["valid"] = df["completed"] & df["chosen"].isin(tickers)
    df["invalid"] = df["completed"] & ~df["valid"]
    return df, model


# ---------------- cost / regret ----------------

def regret_lookup(by):
    sets = {}
    for t, f in by.items():
        sets.setdefault(f["index_tracked"], []).append(
            cost.FundCost(t, float(f["expense_ratio_pct"]), float(f["tracking_difference_5y_pct"])))
    reg, reg_er, dom = {}, {}, set()
    for members in sets.values():
        dom |= set(cost.dominated_funds(members))
        for m in members:
            reg[m.ticker] = cost.regret_bps(m.ticker, members)
            reg_er[m.ticker] = cost.regret_bps(m.ticker, members, cost.cost_er_only_bps)
    in_set = {t for m in sets.values() if len(m) > 1 for t in (f.ticker for f in m)}
    nasdaq = {t for t, f in by.items() if f["cluster"] == "nasdaq100"}
    # sensitivity: ER-only regret for the Nasdaq-100 set, net-cost regret elsewhere
    reg_sens = {t: (reg_er[t] if t in nasdaq else reg[t]) for t in reg}
    return reg, reg_sens, dom, in_set


def add_outcomes(df, by, invalid_as_zero=False):
    reg, reg_sens, dom, in_set = regret_lookup(by)
    v = df["valid"]
    df.loc[v, "regret"] = df.loc[v, "chosen"].map(reg)
    df.loc[v, "regret_sens"] = df.loc[v, "chosen"].map(reg_sens)
    df.loc[v, "suboptimal"] = df.loc[v, "regret"].map(cost.is_suboptimal).astype(float)
    df.loc[v, "dominated"] = df.loc[v, "chosen"].isin(dom).astype(float)
    df.loc[v, "in_set"] = df.loc[v, "chosen"].isin(in_set).astype(float)
    df.loc[v, "cluster"] = df.loc[v, "chosen"].map(lambda t: by[t]["cluster"])
    codes = df["reasoning"].map(rc.code_reasoning)
    for c in rc.CODES + ["cites_cost"]:
        df[c] = codes.map(lambda d, c=c: d[c])
    df["incl"] = df["valid"]                       # rows in share / regret / test denominators
    if invalid_as_zero:                            # sensitivity: invalid = non-target pick with regret 0
        inv = df["invalid"]
        df.loc[inv, ["regret", "regret_sens", "suboptimal", "dominated", "in_set"]] = 0.0
        df.loc[inv, "cluster"] = "invalid"
        df.loc[inv, "chosen"] = "INVALID"
        df["incl"] = df["valid"] | inv
    return df


# ---------------- statistics ----------------

def wilson(k, n):
    if n == 0:
        return (np.nan, np.nan)
    return proportion_confint(k, n, alpha=ALPHA, method="wilson")


def boot_mean_ci(x, rng):
    x = np.asarray(x, float)
    if len(x) == 0:
        return (np.nan, np.nan)
    m = rng.choice(x, size=(N_BOOT, len(x))).mean(axis=1)
    return tuple(np.percentile(m, [2.5, 97.5]))


def boot_diff_ci(a, b, rng):
    a, b = np.asarray(a, float), np.asarray(b, float)
    d = rng.choice(a, (N_BOOT, len(a))).mean(1) - rng.choice(b, (N_BOOT, len(b))).mean(1)
    return tuple(np.percentile(d, [2.5, 97.5]))


def perm_diff_p(a, b, direction, rng):
    """Permutation p for mean(a) - mean(b); direction 'greater', 'less' or 'two-sided'."""
    a, b = np.asarray(a, float), np.asarray(b, float)
    pooled, na = np.concatenate([a, b]), len(a)
    obs = a.mean() - b.mean()
    perms = rng.permuted(np.tile(pooled, (N_PERM, 1)), axis=1)
    d = perms[:, :na].mean(1) - perms[:, na:].mean(1)
    k = {"greater": (d >= obs - 1e-12), "less": (d <= obs + 1e-12),
         "two-sided": (np.abs(d) >= abs(obs) - 1e-12)}[direction].sum()
    return (k + 1) / (N_PERM + 1)


def hc3_diff_p(a, b, direction):
    y = np.concatenate([a, b]).astype(float)
    x = sm.add_constant(np.r_[np.ones(len(a)), np.zeros(len(b))])
    try:
        res = sm.OLS(y, x).fit(cov_type="HC3")
        t, p2 = res.tvalues[1], res.pvalues[1]
    except Exception:  # noqa: BLE001
        return np.nan
    if not np.isfinite(t):
        return np.nan
    if direction == "two-sided":
        return p2
    return p2 / 2 if (t > 0) == (direction == "greater") else 1 - p2 / 2


def f_stat(y, g, k):
    means = np.array([y[g == i].mean() for i in range(k)])
    ns = np.array([(g == i).sum() for i in range(k)])
    between = (ns * (means - y.mean()) ** 2).sum() / (k - 1)
    within = sum(((y[g == i] - means[i]) ** 2).sum() for i in range(k)) / (len(y) - k)
    return between / within if within > 0 else (np.inf if between > 0 else 0.0)


def perm_f_p(groups, rng):
    y = np.concatenate(groups).astype(float)
    g = np.concatenate([np.full(len(x), i) for i, x in enumerate(groups)])
    k, obs = len(groups), f_stat(y, g, len(groups))
    hits = sum(f_stat(y, rng.permutation(g), k) >= obs - 1e-12 for _ in range(N_PERM))
    return obs, (hits + 1) / (N_PERM + 1)


def hc3_f_p(groups):
    y = np.concatenate(groups).astype(float)
    g = np.concatenate([np.full(len(x), i) for i, x in enumerate(groups)])
    x = sm.add_constant(np.column_stack([(g == i).astype(float) for i in range(1, len(groups))]))
    try:
        res = sm.OLS(y, x).fit(cov_type="HC3")
        r = np.eye(x.shape[1])[1:]
        return float(res.f_test(r).pvalue)
    except Exception:  # noqa: BLE001
        return np.nan


def chi2_stat(labels, cats):
    """labels: 0/1 ints; cats: category ints 0..K-1 -> (chi-square statistic, 2 x K table)."""
    k = int(cats.max()) + 1
    tab = np.vstack([np.bincount(cats[labels == i], minlength=k) for i in (0, 1)]).astype(float)
    tab = tab[:, tab.sum(0) > 0]
    exp = tab.sum(1, keepdims=True) * tab.sum(0, keepdims=True) / tab.sum()
    return float(((tab - exp) ** 2 / exp).sum()), tab


def perm_chi2_p(a, b, rng):
    _, cats = np.unique(np.concatenate([a, b]), return_inverse=True)
    labels = np.r_[np.zeros(len(a), int), np.ones(len(b), int)]
    obs, tab = chi2_stat(labels, cats)
    hits = sum(chi2_stat(rng.permutation(labels), cats)[0] >= obs - 1e-9 for _ in range(N_PERM))
    v = np.sqrt(obs / (tab.sum() * (min(tab.shape) - 1))) if min(tab.shape) > 1 else np.nan
    return obs, v, (hits + 1) / (N_PERM + 1)


# ---------------- gate ----------------

def expected_runs(cond_id, override):
    if override:
        return override
    rows = {c["condition_id"]: int(c["runs"]) for c in render.load_conditions()}
    return rows.get(cond_id)


def gate(df, funds, out, override_runs=None):
    lines, fails = [], []
    for cond_id, g in df.groupby("condition_id", sort=False):
        planned = expected_runs(cond_id, override_runs)
        done = int(g["completed"].sum())
        names = name_map(funds, g["naming"].iloc[0])
        cls = mism = 0
        for _, r in g[g["valid"]].iterrows():
            t, _ = recommended_fund(r["reasoning"] or "", names)
            if t:
                cls += 1
                mism += int(t != r["chosen"])
        cut = int(g["cutoff"].sum())
        checks = {"planned=completed": planned is not None and done == planned,
                  "name-vs-ID<=2%": (mism / cls if cls else 0) <= GATE_MAX,
                  "cut-off<=2%": cut / max(len(g), 1) <= GATE_MAX}
        lines.append(f"{cond_id:<24} planned {planned} completed {done} | name/ID {mism}/{cls} | cut-off {cut} | "
                     f"invalid (flagged) {int(g['invalid'].sum())} | "
                     + " ".join(f"{k}:{'PASS' if v else 'FAIL'}" for k, v in checks.items()))
        fails += [f"{cond_id}: {k}" for k, v in checks.items() if not v]
    pool = df[df["completed"]].sort_values("run_id")
    sample = pool.sample(n=min(20, len(pool)), random_state=SEED) if len(pool) else pool
    with open(out / "sample_20.txt", "w") as f:
        for _, r in sample.iterrows():
            f.write(f"--- {r['run_id']} (chosen {r['chosen']})\n{r['raw_response']}\n\n")
    verdict = "PASS" if not fails else "FAIL: " + "; ".join(fails)
    (out / "gate.txt").write_text("\n".join(lines) + f"\n\nGATE: {verdict}\n")
    return not fails, verdict


# ---------------- tables ----------------

def cell_order(df):
    known = [c["condition_id"] for c in render.load_conditions()]
    cells = list(dict.fromkeys(df["cell"]))
    return sorted(cells, key=lambda c: known.index(c) if c in known else len(known))


def shares_tables(df, cells, by):
    rows_c, rows_f = [], []
    for cell in cells:
        g = df[(df["cell"] == cell) & df["completed"]]
        v = g[g["incl"]]
        for cl in CLUSTERS:
            k = int((v["cluster"] == cl).sum())
            rows_c.append({"cell": cell, "category": cl, "n": k, "denominator": len(v),
                           "share": k / len(v) if len(v) else np.nan, **_ci(k, len(v))})
        k = int(g["invalid"].sum())
        rows_c.append({"cell": cell, "category": "invalid (flagged; share of completed calls)", "n": k,
                       "denominator": len(g), "share": k / len(g) if len(g) else np.nan, **_ci(k, len(g))})
        for t in by:
            k = int((v["chosen"] == t).sum())
            rows_f.append({"cell": cell, "ticker": t, "cluster": by[t]["cluster"], "n": k, "denominator": len(v),
                           "share": k / len(v) if len(v) else np.nan, **_ci(k, len(v))})
    return pd.DataFrame(rows_c), pd.DataFrame(rows_f)


def _ci(k, n):
    lo, hi = wilson(k, n)
    return {"ci_lo": lo, "ci_hi": hi}


def regret_table(df, cells, rng):
    rows = []
    for cell in cells:
        g = df[(df["cell"] == cell) & df["completed"]]
        v = g[g["incl"]]
        n = len(v)
        lo, hi = boot_mean_ci(v["regret"], rng)
        k_sub, k_dom = int(v["suboptimal"].sum()), int(v["dominated"].sum())
        s_lo, s_hi = wilson(k_sub, n)
        d_lo, d_hi = wilson(k_dom, n)
        ins = v[v["in_set"] == 1]
        rows.append({"cell": cell, "n_completed": len(g), "n_valid": int(g["valid"].sum()), "n_invalid": int(g["invalid"].sum()),
                     "invalid_rate": g["invalid"].mean() if len(g) else np.nan,
                     "mean_regret_bps": v["regret"].mean() if n else np.nan, "regret_ci_lo": lo, "regret_ci_hi": hi,
                     "suboptimal_n": k_sub, "suboptimal_rate": k_sub / n if n else np.nan,
                     "suboptimal_ci_lo": s_lo, "suboptimal_ci_hi": s_hi,
                     "dominated_n": k_dom, "dominated_rate": k_dom / n if n else np.nan,
                     "dominated_ci_lo": d_lo, "dominated_ci_hi": d_hi,
                     "n_in_same_index_sets": len(ins),
                     "mean_regret_in_sets_bps": ins["regret"].mean() if len(ins) else np.nan,
                     "mean_regret_sens_nasdaq_er_only_bps": v["regret_sens"].mean() if n else np.nan})
    return pd.DataFrame(rows)


def reasoning_tables(df, cells):
    rows = []
    for cell in cells:
        v = df[(df["cell"] == cell) & df["valid"]]
        for c in rc.CODES + ["cites_cost"]:
            k = int(v[c].sum())
            rows.append({"cell": cell, "code": c, "n": k, "denominator": len(v),
                         "rate": k / len(v) if len(v) else np.nan, **_ci(k, len(v)),
                         "note": "rule-based; usable in results only if kappa >= 0.7 vs hand coding (§4.3)"})
    rows2 = []
    ins = df[df["valid"] & (df["in_set"] == 1)]
    for cc in (1, 0):
        g = ins[ins["cites_cost"] == cc]
        k = int((g["regret"] == 0).sum())
        rows2.append({"cites_cost": cc, "n_in_set_picks": len(g), "zero_regret_n": k,
                      "zero_regret_rate": k / len(g) if len(g) else np.nan, **_ci(k, len(g)),
                      "note": "exploratory (§8): does citing cost predict zero regret; pooled over cells"})
    return pd.DataFrame(rows), pd.DataFrame(rows2)


def tests_table(df, rng):
    v = df[df["incl"]]
    get = lambda cell: v.loc[v["cell"] == cell, "regret"].to_numpy(float)  # noqa: E731
    rows = []
    base = get("baseline__real")
    if len(base):
        k = int(v.loc[v["cell"] == "baseline__real", "suboptimal"].sum())
        lo, hi = boot_mean_ci(base, rng)
        rows.append({"hypothesis": "H1", "contrast": "baseline__real", "outcome": "mean regret (bps)",
                     "test": "estimate only", "estimate": base.mean(), "ci_lo": lo, "ci_hi": hi, "n1": len(base)})
        s_lo, s_hi = wilson(k, len(base))
        rows.append({"hypothesis": "H1", "contrast": "baseline__real", "outcome": "suboptimal rate (regret > 2 bp)",
                     "test": "estimate only", "estimate": k / len(base), "ci_lo": s_lo, "ci_hi": s_hi, "n1": len(base)})
    for hid, cell, ref, direction in HYPOTHESES:
        a, b = get(cell), get(ref)
        if not len(a) or not len(b):
            rows.append({"hypothesis": hid, "contrast": f"{cell} - {ref}", "in_family": True, "p_perm": 1.0, "missing": True,
                         "note": "MISSING (p set to 1; interim): cell missing from this log"})
            continue
        lo, hi = boot_diff_ci(a, b, rng)
        rows.append({"hypothesis": hid, "contrast": f"{cell} - {ref}", "outcome": "mean regret difference (bps)",
                     "test": f"permutation, one-sided ({direction})", "direction": direction,
                     "estimate": a.mean() - b.mean(), "ci_lo": lo, "ci_hi": hi,
                     "p_perm": perm_diff_p(a, b, direction, rng), "p_hc3": hc3_diff_p(a, b, direction),
                     "n1": len(a), "n2": len(b), "in_family": True})
    groups = [get(c) for c in ORDER_CELLS]
    if all(len(x) for x in groups):
        fobs, p = perm_f_p(groups, rng)
        means = [x.mean() for x in groups]
        rows.append({"hypothesis": "H4", "contrast": " vs ".join(ORDER_CELLS), "outcome": "mean regret across orders",
                     "test": "permutation one-way F (two-sided)", "estimate": max(means) - min(means),
                     "note": "estimate = max - min of order means; F = %.3f; means = %s" % (fobs, [round(float(m), 3) for m in means]),
                     "p_perm": p, "p_hc3": hc3_f_p(groups), "n1": sum(map(len, groups)), "in_family": True})
    else:
        rows.append({"hypothesis": "H4", "contrast": " vs ".join(ORDER_CELLS), "in_family": True, "p_perm": 1.0, "missing": True,
                     "note": "MISSING (p set to 1; interim): order cells missing from this log"})
    ra = v.loc[v["cell"] == "baseline__real", "chosen"].to_numpy()
    rm_ = v.loc[v["cell"] == "baseline__masked", "chosen"].to_numpy()
    if len(ra) and len(rm_):
        chi, cv, p = perm_chi2_p(ra, rm_, rng)
        rows.append({"hypothesis": "H5", "contrast": "baseline__real vs baseline__masked",
                     "outcome": "per-fund pick distribution", "test": "permutation chi-square (two-sided)",
                     "estimate": cv, "note": f"estimate = Cramer's V; chi2 = {chi:.2f}", "p_perm": p,
                     "n1": len(ra), "n2": len(rm_), "in_family": True})
        a, b = get("baseline__real"), get("baseline__masked")
        lo, hi = boot_diff_ci(a, b, rng)
        rows.append({"hypothesis": "H5 (secondary)", "contrast": "baseline__real - baseline__masked",
                     "outcome": "mean regret difference (bps)", "test": "permutation, two-sided",
                     "estimate": a.mean() - b.mean(), "ci_lo": lo, "ci_hi": hi,
                     "p_perm": perm_diff_p(a, b, "two-sided", rng), "p_hc3": hc3_diff_p(a, b, "two-sided"),
                     "n1": len(a), "n2": len(b), "in_family": False, "note": "reported outside the Holm family"})
    else:
        rows.append({"hypothesis": "H5", "contrast": "baseline__real vs baseline__masked", "in_family": True, "p_perm": 1.0, "missing": True,
                     "note": "MISSING (p set to 1; interim): baseline cells missing from this log"})
    t = pd.DataFrame(rows)
    for col in ("in_family", "p_perm", "p_hc3", "note", "missing"):
        if col not in t:
            t[col] = np.nan
    t["in_family"] = t["in_family"].fillna(False).astype(bool)
    t["missing"] = t["missing"].fillna(False).astype(bool)
    fam = t["in_family"]
    assert fam.sum() == FAMILY_SIZE, "the Holm family must always have 6 tests"
    t["interim"] = bool(t["missing"].any())
    t["p_holm"], t["reject_holm_0.05"] = np.nan, pd.Series([None] * len(t), dtype=object)
    if fam.any():
        rej, padj, _, _ = multipletests(t.loc[fam, "p_perm"], alpha=ALPHA, method="holm")
        t.loc[fam, "p_holm"] = padj
        t.loc[fam, "reject_holm_0.05"] = rej
    return t


# ---------------- summary ----------------

def summary(model, path, df, verdict, reg, tests, out, invalid_as_zero=False):
    f = lambda x: "NA" if pd.isna(x) else f"{x:.3f}"  # noqa: E731
    n_miss = int(tests["missing"].sum())
    L = ([f"INTERIM: {n_miss} of {FAMILY_SIZE} confirmatory tests missing from this log; each counted in the "
          f"Holm family with p = 1."] if n_miss else [])
    L += (["SENSITIVITY: invalid picks counted as non-target picks with regret 0 (in all share, regret and "
           "test denominators)."] if invalid_as_zero else [])
    L += [f"Study 1 v2 analysis: model {model}", f"log: {path}", f"quality gate: {verdict}",
         f"calls: {len(df)} planned rows, {int(df['completed'].sum())} completed, "
         f"{int(df['valid'].sum())} valid picks, {int(df['invalid'].sum())} invalid (flagged)", "",
         "Tests (one Holm family over the rows marked *; Holm uses p_perm):"]
    for _, r in tests.iterrows():
        star = "*" if r["in_family"] else " "
        L.append(f" {star} {r['hypothesis']:<15} {str(r.get('contrast')):<38} est {f(r.get('estimate'))} "
                 f"CI [{f(r.get('ci_lo'))}, {f(r.get('ci_hi'))}] p_perm {f(r.get('p_perm'))} "
                 f"p_hc3 {f(r.get('p_hc3'))} p_holm {f(r.get('p_holm'))}"
                 + (f"  ({r['note']})" if isinstance(r.get("note"), str) else ""))
    L += ["", "Regret by cell (bps; ≤ 2 bp tie rule; suboptimal = regret > 2 bp):"]
    for _, r in reg.iterrows():
        L.append(f"   {r['cell']:<20} n {r['n_valid']:>4}  mean {f(r['mean_regret_bps'])} "
                 f"[{f(r['regret_ci_lo'])}, {f(r['regret_ci_hi'])}]  suboptimal {f(r['suboptimal_rate'])}  "
                 f"invalid {f(r['invalid_rate'])}")
    L += ["", "Choices where §8 is silent: invalid picks are their own category and excluded from share,",
          "regret and test denominators; Holm on permutation p; H5 = per-fund pick distribution (chi-square);",
          "regret 0 for funds with no same-index peer; reasoning codes are rule-based (kappa check pending).",
          "Tables: shares_cluster.csv, shares_fund.csv, regret_by_condition.csv, tests.csv,",
          "reasoning_codes.csv, cost_codes_vs_regret.csv, gate.txt, sample_20.txt."]
    (out / "summary.txt").write_text("\n".join(L) + "\n")


def run(path, model=None, out=None, confirm_final=False, expected=None, invalid_as_zero=False):
    guard(path, confirm_final)
    funds, by = funds_table()
    df, model = load_log(path, model, funds)
    out = Path(out or ROOT / "results" / "v2_analysis" / model)
    if invalid_as_zero:
        out = out / "sensitivity_invalid_as_zero"
    out.mkdir(parents=True, exist_ok=True)
    ok, verdict = gate(df, funds, out, expected)
    if not ok:
        (out / "summary.txt").write_text(f"Quality gate failed; analysis not run.\n{verdict}\nSee gate.txt.\n")
        return False, out
    df = add_outcomes(df, by, invalid_as_zero)
    rng = np.random.default_rng(SEED)
    random.seed(SEED)
    cells = cell_order(df)
    sc, sf = shares_tables(df, cells, by)
    reg = regret_table(df, cells, rng)
    codes, cost_vs = reasoning_tables(df, cells)
    tests = tests_table(df, rng)
    for name, t in [("shares_cluster", sc), ("shares_fund", sf), ("regret_by_condition", reg),
                    ("tests", tests), ("reasoning_codes", codes), ("cost_codes_vs_regret", cost_vs)]:
        t.to_csv(out / f"{name}.csv", index=False, quoting=csv.QUOTE_MINIMAL)
    summary(model, path, df, verdict, reg, tests, out, invalid_as_zero)
    return True, out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("log")
    ap.add_argument("--model")
    ap.add_argument("--out")
    ap.add_argument("--expected-runs", type=int, help="planned runs per cell (default: data/conditions_v2.csv)")
    ap.add_argument("--confirm-final", action="store_true")
    ap.add_argument("--invalid-as-zero", action="store_true",
                    help="sensitivity: invalid picks = non-target, regret 0; outputs in <out>/sensitivity_invalid_as_zero")
    a = ap.parse_args()
    try:
        ok, out = run(a.log, a.model, a.out, a.confirm_final, a.expected_runs, a.invalid_as_zero)
    except GuardError as e:
        sys.exit(f"REFUSED: {e}")
    print(f"{'done' if ok else 'STOPPED: quality gate failed'}; outputs in {out}")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
