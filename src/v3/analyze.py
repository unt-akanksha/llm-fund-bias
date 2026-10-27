"""Study 1 v3 analysis (docs/design_v3.md §5). One model per call; families analyzed separately.

  python src/v3/analyze.py --model gpt-5.4 [--replace]        # -> results/v3_analysis/<model>/
  python src/v3/analyze.py --scaling [--replace]              # -> results/v3_analysis/scaling.csv (all models)
  python src/v3/analyze.py --model gpt-5.4 --families all     # Amendment v3-3 -> results/v3_1_analysis/<model>/

Default families are sp500 and ndx (the submitted v3 results, unchanged). Any other family list writes under
results/v3_1_analysis/ so the submitted results are never overwritten.

Reads runs/raw_v3/main_<model>.jsonl. Writes only under results/v3_analysis/ and refuses to write into a
non-empty folder unless --replace. v2 code is imported read-only (regret, CIs, name-vs-ID detector).

Quality gate first (Amendment v3-2): planned = completed per cell; name-vs-ID mismatch <= 2% after recorded
manual reviews (data/gate_reviews_v3.csv) and cut-offs <= 2%, both per model x family. Invalid picks (not in the family's table) are flagged, reported,
and excluded from denominators. The analysis stops if the reviewed gate fails.

Outputs per model: gate.txt, sample_20.txt, cells.csv (every cell), pooled.csv (family x context, and family x
context x system), tests.csv (H2 x3, H3, HF with Holm per family; HT per document), summary.txt.
"""

import argparse
import csv
import json
import random
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact
from statsmodels.stats.multitest import multipletests
from statsmodels.stats.proportion import confint_proportions_2indep, proportion_confint

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from name_id_check import recommended_fund  # noqa: E402

from v2 import analyze as v2a, render  # noqa: E402
from v3 import prompts  # noqa: E402

LOGDIR = ROOT / "runs" / "raw_v3"
OUTROOT = ROOT / "results" / "v3_analysis"
OUTROOT_EXT = ROOT / "results" / "v3_1_analysis"   # Amendment v3-3 (any family list other than the original)
REVIEWS = ROOT / "data" / "gate_reviews_v3.csv"
GATE_MAX = 0.02
SEED = 20261021
BIASED = ["D3", "D5", "D7"]


def wilson(k, n):
    return proportion_confint(k, n, method="wilson") if n else (np.nan, np.nan)


def rd_ci(k1, n1, k2, n2):
    """Risk difference p1 - p2 with Newcombe 95% CI."""
    if not n1 or not n2:
        return np.nan, np.nan, np.nan
    lo, hi = confint_proportions_2indep(k1, n1, k2, n2, method="newcomb", compare="diff")
    return k1 / n1 - k2 / n2, lo, hi


def fisher_one_sided(k1, n1, k2, n2, direction):
    """H1: p1 > p2 ('greater') or p1 < p2 ('less')."""
    return fisher_exact([[k1, n1 - k1], [k2, n2 - k2]], alternative=direction)[1]


def safe_out(path):
    path = Path(path).resolve()
    roots = [OUTROOT.resolve(), OUTROOT_EXT.resolve()]
    if not any(r == path or r in path.parents for r in roots):
        raise ValueError(f"refusing to write outside {OUTROOT} and {OUTROOT_EXT}: {path}")
    return path


def prepare_out(path, replace):
    path = safe_out(path)
    if path.exists() and any(path.iterdir()) and not replace:
        sys.exit(f"REFUSED: {path} exists and is not empty (pass --replace)")
    path.mkdir(parents=True, exist_ok=True)
    return path


# ---------------- load ----------------

RUNS = {"openai": 30, "anthropic": 30, "ollama": 50}     # Amendment v3-1: runs per cell analyzed, by vendor


def planned_runs(model):
    import yaml
    cfg = yaml.safe_load(open(ROOT / "config" / "models_v3.yaml"))
    return RUNS[cfg["models"][model]["provider"]] if model in cfg["models"] else prompts.RUNS_PER_CELL


def resolve_families(arg=None):
    """None/'' -> original v3 families; 'all' -> every family; 'ext' -> Amendment v3-3 families; else comma list."""
    if not arg:
        return list(prompts.ORIGINAL_FAMILIES)
    if arg == "all":
        return list(prompts.FAMILIES)
    if arg == "ext":
        return [f for f in prompts.FAMILIES if f not in prompts.ORIGINAL_FAMILIES]
    fams = [f for f in arg.split(",") if f]
    unknown = set(fams) - set(prompts.FAMILIES)
    if unknown:
        raise ValueError(f"unknown families: {sorted(unknown)}")
    return fams


def load(model, log=None, runs=None, families=None):
    families = families or resolve_families()
    log = Path(log or LOGDIR / f"main_{model}.jsonl")
    runs = runs or planned_runs(model)
    rows = {}
    for line in open(log):
        r = json.loads(line)
        if r.get("model_key") != model or r["run_index"] >= runs:     # only runs 0..runs-1 are analyzed
            continue
        if r["family"] not in families:
            continue
        if r["run_id"] not in rows or not r.get("error"):
            rows[r["run_id"]] = r                       # a later successful retry wins
    df = pd.DataFrame(rows.values())
    df["completed"] = df["error"].isna()
    df["cutoff"] = df.get("hit_output_cap", False).fillna(False).astype(bool) if "hit_output_cap" in df else False
    fam_tickers = {f: set(v["tickers"]) for f, v in prompts.FAMILIES.items()}
    df["valid"] = df["completed"] & df.apply(lambda r: r.get("chosen_ticker") in fam_tickers[r["family"]], axis=1)
    df["invalid"] = df["completed"] & ~df["valid"]
    return df


def add_outcomes(df):
    by = {f["ticker"]: f for f in prompts.load_all_funds()}
    reg, reg_sens, dom, _ = v2a.regret_lookup(by)
    v = df["valid"]
    df.loc[v, "regret"] = df.loc[v, "chosen_ticker"].map(reg)
    df.loc[v, "regret_er_only"] = df.loc[v, "chosen_ticker"].map(reg_sens)
    df["costlier"] = df.apply(lambda r: r["valid"] and r["chosen_ticker"] == prompts.FAMILIES[r["family"]]["worst"], axis=1)
    df["best"] = df.apply(lambda r: r["valid"] and r["chosen_ticker"] == prompts.FAMILIES[r["family"]]["best"], axis=1)
    return df


# ---------------- gate ----------------

def family_names(family):
    funds = prompts.family_funds(family)
    out = {}
    for f in funds:
        out[re.escape(f["fund_name"])] = f["ticker"]
        out[f["ticker"]] = f["ticker"]
    return out


def load_reviews():
    """-> (run IDs cleared as false positives, run IDs reviewed and confirmed as real mismatches)."""
    if not REVIEWS.exists():
        return set(), set()
    rows = list(csv.DictReader(open(REVIEWS)))
    return ({r["run_id"] for r in rows if r["verdict"].strip() == "false_positive"},
            {r["run_id"] for r in rows if r["verdict"].strip() == "real_mismatch"})


def gate(df, out, runs, families=None):
    """Amendment v3-2: planned = completed is checked per cell; the 2% limits on name-vs-ID mismatches and
    cut-offs are checked per model x family (all 20 cells of a family pooled), because at 30 runs per cell a
    single case exceeds 2%. Every cell is still reported, and every real mismatch is listed."""
    families = families or resolve_families()
    cleared, confirmed = load_reviews()
    conds = {k: c for k, c in prompts.load_conditions().items() if c["family"] in families}
    lines, fails, fails_rev, flagged_all, cleared_used, confirmed_used = [], [], [], [], [], []
    fam = {f: {"cls": 0, "m": 0, "m_rev": 0, "cut": 0, "n": 0} for f in families}
    for cid in conds:
        g = df[df["condition_id"] == cid]
        done = int(g["completed"].sum())
        names = family_names(conds[cid]["family"])
        cls = 0
        flagged = []
        for _, r in g[g["valid"]].iterrows():
            t, _ = recommended_fund(r.get("reasoning") or "", names)
            if t:
                cls += 1
                if t != r["chosen_ticker"]:
                    flagged.append(r["run_id"])
        cut = int(g["cutoff"].sum()) if len(g) else 0
        rev = [x for x in flagged if x in cleared]
        cleared_used += rev
        confirmed_used += [x for x in flagged if x in confirmed]
        flagged_all += [x for x in flagged if x not in cleared and x not in confirmed]
        f = fam[conds[cid]["family"]]
        f["cls"] += cls; f["m"] += len(flagged); f["m_rev"] += len(flagged) - len(rev); f["cut"] += cut; f["n"] += len(g)
        ok_cell = done == runs
        lines.append(f"{cid:<28} planned {runs} completed {done} | name/ID flagged {len(flagged)}/{cls} "
                     f"(cleared {len(rev)}) | cut-off {cut} | invalid (flagged) {int(g['invalid'].sum())} | "
                     f"planned=completed:{'PASS' if ok_cell else 'FAIL'}")
        if not ok_cell:
            fails.append(f"{cid}: planned=completed")
            fails_rev.append(f"{cid}: planned=completed")
    lines.append("")
    for fname, f in fam.items():
        for key, fs, label in (("m", fails, "original"), ("m_rev", fails_rev, "after manual review")):
            nid = f[key] / f["cls"] if f["cls"] else 0
            cutr = f["cut"] / f["n"] if f["n"] else 0
            lines.append(f"family {fname:<6} [{label}] name/ID {f[key]}/{f['cls']} = {nid:.1%} "
                         f"({'PASS' if nid <= GATE_MAX else 'FAIL'}) | cut-off {f['cut']}/{f['n']} = {cutr:.1%} "
                         f"({'PASS' if cutr <= GATE_MAX else 'FAIL'})")
            if nid > GATE_MAX:
                fs.append(f"family {fname}: name-vs-ID<=2%")
            if cutr > GATE_MAX:
                fs.append(f"family {fname}: cut-off<=2%")
    pool = df[df["completed"]].sort_values("run_id")
    sample = pool.sample(n=min(20, len(pool)), random_state=SEED) if len(pool) else pool
    with open(out / "sample_20.txt", "w") as f:
        for _, r in sample.iterrows():
            f.write(f"--- {r['run_id']} (chosen {r.get('chosen_ticker')})\n{r.get('raw_response')}\n\n")
    v = "PASS" if not fails else "FAIL: " + "; ".join(fails)
    vr = "PASS" if not fails_rev else "FAIL: " + "; ".join(fails_rev)
    note = (f"{len(cleared_used)} flagged response(s) cleared as false positives by manual review ({REVIEWS.name}); "
            f"{len(confirmed_used)} reviewed and confirmed as real mismatches: "
            f"{', '.join(confirmed_used) if confirmed_used else 'none'}")
    unreviewed = f"unreviewed flagged responses: {', '.join(flagged_all) if flagged_all else 'none'}"
    (out / "gate.txt").write_text("Gate rules: Amendment v3-2 (docs/design_v3.md)\n\n" + "\n".join(lines)
                                  + f"\n\nGATE: {v}\nGATE (after manual review): {vr}\n{note}\n{unreviewed}\n")
    return not fails_rev, f"original {v}; after manual review {vr}; {note}", flagged_all


# ---------------- tables ----------------

def share_row(g, extra):
    v = g[g["valid"]]
    n = len(v)
    row = dict(extra, n_completed=int(g["completed"].sum()), n_valid=n, n_invalid=int(g["invalid"].sum()))
    for name in ("costlier", "best"):
        k = int(v[name].sum())
        lo, hi = wilson(k, n)
        row.update({f"{name}_n": k, f"{name}_share": k / n if n else np.nan, f"{name}_ci_lo": lo, f"{name}_ci_hi": hi})
    lo, hi = v2a.boot_mean_ci(v["regret"], np.random.default_rng(SEED)) if n else (np.nan, np.nan)
    row.update({"mean_regret_bps": v["regret"].mean() if n else np.nan, "regret_ci_lo": lo, "regret_ci_hi": hi,
                "mean_regret_er_only_bps": v["regret_er_only"].mean() if n else np.nan})
    for t in sorted(set(v["chosen_ticker"])):
        row[f"pick_{t}"] = int((v["chosen_ticker"] == t).sum())
    return row


def tables(df, families=None):
    families = families or resolve_families()
    cells, pooled = [], []
    for cid, c in prompts.load_conditions().items():
        if c["family"] not in families:
            continue
        cells.append(share_row(df[df["condition_id"] == cid], {k: c[k] for k in ("condition_id", "family", "context",
                                                                               "template", "system", "target")}))
    for fam in families:
        for ctx in prompts.CONTEXTS:
            g = df[(df["family"] == fam) & (df["context"] == ctx)]
            pooled.append(share_row(g, {"family": fam, "context": ctx, "system": "pooled", "template": "pooled"}))
            for sysm in prompts.SYSTEMS:
                pooled.append(share_row(g[g["system"] == sysm], {"family": fam, "context": ctx, "system": sysm,
                                                                 "template": "pooled"}))
            for tpl in prompts.TEMPLATES:
                pooled.append(share_row(g[g["template"] == tpl], {"family": fam, "context": ctx, "system": "pooled",
                                                                  "template": tpl}))
    return pd.DataFrame(cells), pd.DataFrame(pooled)


def counts(df, **sel):
    g = df[df["valid"]]
    for k, v in sel.items():
        g = g[g[k].isin(v if isinstance(v, (list, tuple, set)) else [v])]
    return int(g["costlier"].sum()), len(g)


def tests(df, families=None):
    rows = []
    for fam in families or resolve_families():
        fam_rows = []
        kb, nb = counts(df, family=fam, context="baseline")
        for ctx in BIASED:
            k, n = counts(df, family=fam, context=ctx)
            d, lo, hi = rd_ci(k, n, kb, nb)
            fam_rows.append({"family": fam, "hypothesis": f"H2 ({ctx})", "contrast": f"{ctx} - baseline",
                             "outcome": "costlier-fund share", "estimate": d, "ci_lo": lo, "ci_hi": hi,
                             "p_one_sided": fisher_one_sided(k, n, kb, nb, "greater") if n and nb else np.nan,
                             "k1": k, "n1": n, "k2": kb, "n2": nb})
        k, n = counts(df, family=fam, context="D1")
        d, lo, hi = rd_ci(k, n, kb, nb)
        fam_rows.append({"family": fam, "hypothesis": "H3 (D1)", "contrast": "D1 - baseline",
                         "outcome": "costlier-fund share", "estimate": d, "ci_lo": lo, "ci_hi": hi,
                         "p_one_sided": fisher_one_sided(k, n, kb, nb, "less") if n and nb else np.nan,
                         "k1": k, "n1": n, "k2": kb, "n2": nb})
        kf, nf = counts(df, family=fam, context=BIASED, system="fiduciary")
        ks, ns = counts(df, family=fam, context=BIASED, system="standard")
        d, lo, hi = rd_ci(kf, nf, ks, ns)
        fam_rows.append({"family": fam, "hypothesis": "HF (fiduciary)", "contrast": "fiduciary - standard, biased docs",
                         "outcome": "costlier-fund share", "estimate": d, "ci_lo": lo, "ci_hi": hi,
                         "p_one_sided": fisher_one_sided(kf, nf, ks, ns, "less") if nf and ns else np.nan,
                         "k1": kf, "n1": nf, "k2": ks, "n2": ns})
        ps = [r["p_one_sided"] for r in fam_rows]
        ok = [i for i, p in enumerate(ps) if not np.isnan(p)]
        if ok:
            rej, padj, _, _ = multipletests([ps[i] for i in ok], method="holm")
            for j, i in enumerate(ok):
                fam_rows[i]["p_holm"], fam_rows[i]["reject_holm_0.05"] = padj[j], bool(rej[j])
        rows += fam_rows
        for ctx in BIASED:                                   # HT: template robustness (descriptive)
            est = {}
            for tpl in prompts.TEMPLATES:
                k, n = counts(df, family=fam, context=ctx, template=tpl)
                kb_t, nb_t = counts(df, family=fam, context="baseline", template=tpl)
                est[tpl] = rd_ci(k, n, kb_t, nb_t)
            rows.append({"family": fam, "hypothesis": f"HT ({ctx})", "contrast": "H2 effect under A vs B",
                         "outcome": "costlier-fund share difference (A, B)",
                         "estimate": est["A"][0] - est["B"][0] if not np.isnan(est["A"][0]) else np.nan,
                         "effect_A": est["A"][0], "effect_A_ci": f"[{est['A'][1]:.3f}, {est['A'][2]:.3f}]",
                         "effect_B": est["B"][0], "effect_B_ci": f"[{est['B'][1]:.3f}, {est['B'][2]:.3f}]",
                         "same_sign": bool(np.sign(round(est["A"][0], 6)) == np.sign(round(est["B"][0], 6)))})
    return pd.DataFrame(rows)


def summary(model, verdict, pooled, tst, out, families=None):
    f = lambda x: "  -" if pd.isna(x) else f"{x:.0%}"  # noqa: E731
    L = [f"Study 1 v3 analysis: {model}", f"quality gate: {verdict}", "",
         "Costlier-fund share by context (pooled over templates and system prompts; valid picks):"]
    for fam in families or resolve_families():
        p = pooled[(pooled["family"] == fam) & (pooled["system"] == "pooled") & (pooled["template"] == "pooled")]
        L.append(f"  {fam}: " + "  ".join(f"{r['context']} {f(r['costlier_share'])} (n={r['n_valid']})"
                                          for _, r in p.iterrows()))
    L += ["", "Tests (risk difference in costlier-fund share, Newcombe 95% CI, one-sided Fisher, Holm per family):"]
    for _, r in tst[tst["hypothesis"].str.match(r"H[23F]")].iterrows():
        L.append(f"  {r['family']:<6} {r['hypothesis']:<15} {r['estimate']:+.3f} [{r['ci_lo']:+.3f}, {r['ci_hi']:+.3f}] "
                 f"p={r['p_one_sided']:.4g} holm={r.get('p_holm', np.nan):.4g}")
    (out / "summary.txt").write_text("\n".join(L) + "\n")


def analyze(model, replace=False, log=None, out=None, runs=None, families=None):
    runs = runs or planned_runs(model)
    families = families or resolve_families()
    root = OUTROOT if families == list(prompts.ORIGINAL_FAMILIES) else OUTROOT_EXT
    out = prepare_out(out or root / model, replace)
    df = load(model, log, runs, families)
    ok, verdict, unreviewed = gate(df, out, runs, families)
    if not ok:
        (out / "summary.txt").write_text(f"Quality gate failed; analysis not run.\n{verdict}\nSee gate.txt.\n")
        return False, out, unreviewed
    df = add_outcomes(df)
    cells, pooled = tables(df, families)
    tst = tests(df, families)
    cells.to_csv(out / "cells.csv", index=False)
    pooled.to_csv(out / "pooled.csv", index=False)
    tst.to_csv(out / "tests.csv", index=False)
    fam_note = "" if families == list(prompts.ORIGINAL_FAMILIES) else f"; families: {', '.join(families)}"
    summary(model, f"{verdict}; runs per cell analyzed: {runs}{fam_note}", pooled, tst, out, families)
    return True, out, unreviewed


def scaling(replace=False, root=OUTROOT):
    path = safe_out(root / "scaling.csv")
    if path.exists() and not replace:
        sys.exit(f"REFUSED: {path} exists (pass --replace)")
    import yaml
    cfg = yaml.safe_load(open(ROOT / "config" / "models_v3.yaml"))
    rows = []
    for mk, m in cfg["models"].items():
        p = root / mk / "pooled.csv"
        if not p.exists():
            continue
        d = pd.read_csv(p)
        d = d[(d["system"] == "pooled") & (d["template"] == "pooled")]
        for _, r in d.iterrows():
            rows.append({"model": mk, "vendor": m["provider"], "size": m.get("size"), "family": r["family"],
                         "context": r["context"], "costlier_share": r["costlier_share"],
                         "ci_lo": r["costlier_ci_lo"], "ci_hi": r["costlier_ci_hi"], "n_valid": r["n_valid"],
                         "mean_regret_bps": r["mean_regret_bps"]})
    pd.DataFrame(rows).to_csv(path, index=False)
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model")
    ap.add_argument("--scaling", action="store_true")
    ap.add_argument("--replace", action="store_true")
    ap.add_argument("--matched30", action="store_true",
                    help="matched comparison: runs 0-29 for any model -> <results root>/matched30/<model>")
    ap.add_argument("--families", default="",
                    help="default sp500,ndx (submitted v3); 'all', 'ext' or a comma list -> results/v3_1_analysis/")
    a = ap.parse_args()
    random.seed(SEED)
    fams = resolve_families(a.families)
    root = OUTROOT if fams == list(prompts.ORIGINAL_FAMILIES) else OUTROOT_EXT
    if a.scaling:
        print(f"wrote {scaling(a.replace, root)}")
        return
    if a.matched30:
        ok, out, unreviewed = analyze(a.model, a.replace, out=root / "matched30" / a.model, runs=30, families=fams)
    else:
        ok, out, unreviewed = analyze(a.model, a.replace, families=fams)
    print(("done" if ok else "STOPPED: quality gate failed") + f"; outputs in {out}")
    if unreviewed:
        print(f"{len(unreviewed)} unreviewed name-vs-ID flags (see gate.txt)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
