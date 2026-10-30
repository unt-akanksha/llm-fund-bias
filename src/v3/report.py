"""Study 1 v3 reporting: run all analyses, the scaling figure, and the auto-filled results summary.

  python src/v3/report.py --analyze-all [--runs claude-sonnet-5.5=20] [--replace]
        each model with a log: main analysis (own run count) and matched comparison (runs 0-29)
  python src/v3/report.py --figures [--replace]       results/v3_analysis/figures/scaling_<family>.png/.pdf
  python src/v3/report.py --summary [--replace]       results/v3_analysis/RESULTS_SUMMARY.md
  python src/v3/report.py --families all --analyze-all --figures --summary [--replace]
        Amendment v3-3 (four families, gpt-6 added) -> results/v3_1_analysis/

Reads only the analysis outputs (pooled.csv, tests.csv, gate.txt); writes only under results/v3_analysis/ or,
with --families, results/v3_1_analysis/. The default (original families sp500, ndx, the 8 v3 models) reproduces
the submitted v3 report.
A model whose gate failed is listed as such and left out of figures and tables.
"""

import argparse
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from v3 import analyze as an, prompts  # noqa: E402

SIZES = ["small", "mid", "large"]
VENDOR_LABEL = {"openai": "OpenAI (nano / mini / gpt-5.4)", "anthropic": "Anthropic (Haiku / Sonnet / Opus 5.5)",
                "ollama": "Qwen 2.5 local (7B / 14B)", "openai-gpt6": "OpenAI gpt-6 (Luna / Sol / Astra)"}
FAMILY_LABEL = {"sp500": "S&P 500 (SPY vs IVV vs VOO)", "ndx": "Nasdaq-100 (QQQ vs QQQM)",
                "russell2000": "Russell 2000 (IWM vs VTWO)", "dow30": "Dow 30 (RYDHX vs DIA)"}
FAMILY_SHORT = {"sp500": "S&P 500", "ndx": "Nasdaq-100", "russell2000": "Russell 2000", "dow30": "Dow 30"}
EXT_ORDER = ["sp500", "ndx", "russell2000", "dow30"]   # small-gap families first; dow30 (large gap) last
GPT6 = {"gpt-6-luna": "gpt-5.4-nano", "gpt-6-sol": "gpt-5.4-mini", "gpt-6-astra": "gpt-5.4"}


def models_cfg(ext=False):
    """All models (ext) or the 8 models of the submitted v3 report (gpt-6 was added by Amendment v3-3)."""
    cfg = yaml.safe_load(open(ROOT / "config" / "models_v3.yaml"))["models"]
    return cfg if ext else {k: v for k, v in cfg.items() if k not in GPT6}


def is_ext(families):
    return list(families) != list(prompts.ORIGINAL_FAMILIES)


def line_of(mk, m):
    """Plot/series key: vendor, with gpt-6 as its own generation line."""
    return "openai-gpt6" if mk in GPT6 else m["provider"]


def setup(families_arg=None):
    """(families, outroot or None for the submitted root, cfg)."""
    fams = an.resolve_families(families_arg)
    if fams == list(prompts.ORIGINAL_FAMILIES):
        return fams, None, models_cfg()
    return [f for f in EXT_ORDER if f in fams], an.OUTROOT_EXT, models_cfg(ext=True)


def model_dir(mk, matched=False, outroot=None):
    root = Path(outroot or an.OUTROOT)
    return root / "matched30" / mk if matched else root / mk


def analyze_all(replace=False, runs_override=None, families=None, outroot=None, cfg=None):
    runs_override = runs_override or {}
    out = []
    for mk in cfg or models_cfg():
        if not (an.LOGDIR / f"main_{mk}.jsonl").exists():
            out.append((mk, "no log"))
            continue
        runs = runs_override.get(mk)
        ok, d, unrev = an.analyze(mk, replace=replace, runs=runs, families=families)
        ok30, _, _ = an.analyze(mk, replace=replace, out=model_dir(mk, matched=True, outroot=outroot), runs=30,
                                families=families)
        out.append((mk, f"main {'PASS' if ok else 'GATE FAIL'} (runs {runs or an.planned_runs(mk)}); "
                        f"matched30 {'PASS' if ok30 else 'GATE FAIL'}; unreviewed flags {len(unrev)}"))
    return out


def biased_share(pooled, family):
    """Costlier-fund share pooled over D3, D5, D7 (templates and system prompts pooled), Wilson CI."""
    p = pooled[(pooled["family"] == family) & (pooled["system"] == "pooled") & (pooled["template"] == "pooled")]
    b = p[p["context"].isin(an.BIASED)]
    k, n = int(b["costlier_n"].sum()), int(b["n_valid"].sum())
    lo, hi = an.wilson(k, n)
    base = p[p["context"] == "baseline"].iloc[0]
    return {"k": k, "n": n, "share": k / n if n else np.nan, "lo": lo, "hi": hi,
            "baseline_share": base["costlier_share"], "baseline_lo": base["costlier_ci_lo"],
            "baseline_hi": base["costlier_ci_hi"]}


def biased_regret(pooled, family):
    """Mean 5-year cost regret (bp) over valid picks under D3, D5, D7, and with no document."""
    p = pooled[(pooled["family"] == family) & (pooled["system"] == "pooled") & (pooled["template"] == "pooled")]
    b = p[p["context"].isin(an.BIASED)]
    base = p[p["context"] == "baseline"].iloc[0]
    return (b["mean_regret_bps"] * b["n_valid"]).sum() / b["n_valid"].sum(), base["mean_regret_bps"]


def gate_passed(d):
    g = d / "gate.txt"
    return g.exists() and "GATE (after manual review): PASS" in g.read_text() and (d / "pooled.csv").exists()


def collect(matched=False, outroot=None, cfg=None, families=None):
    cfg = cfg or models_cfg()
    families = families or prompts.ORIGINAL_FAMILIES
    rows, skipped = [], []
    for mk, m in cfg.items():
        d = model_dir(mk, matched, outroot)
        if not gate_passed(d):
            skipped.append(mk)
            continue
        pooled = pd.read_csv(d / "pooled.csv")
        for fam in families:
            row = {"model": mk, "vendor": m["provider"], "size": m.get("size"), "family": fam,
                   **biased_share(pooled, fam)}
            if is_ext(families):
                row["line"] = line_of(mk, m)
            rows.append(row)
    return pd.DataFrame(rows), skipped


def _scaling_panel(ax, d, key):
    nlines = d[key].nunique()
    for j, (vendor, g) in enumerate(d.groupby(key, sort=False)):
        g = g.assign(x=g["size"].map({s: i for i, s in enumerate(SIZES)})).sort_values("x")
        off = (j - 1) * 0.08 if nlines <= 3 else (j - (nlines - 1) / 2) * 0.07
        eb = ax.errorbar(g["x"] + off, g["share"], yerr=[(g["share"] - g["lo"]).clip(lower=0), (g["hi"] - g["share"]).clip(lower=0)], marker="o",
                         capsize=3, label=VENDOR_LABEL.get(vendor, vendor))
        ax.scatter(g["x"] + off, g["baseline_share"], marker="o", s=36, facecolors="none",
                   edgecolors=eb[0].get_color(), linewidths=1.2, zorder=3)
    ax.set_xticks(range(len(SIZES)), ["small", "mid", "large"])
    ax.set_ylim(-0.03, 1.03)


def figures(replace=False, outroot=None, cfg=None, families=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    families = families or prompts.ORIGINAL_FAMILIES
    outdir = an.safe_out(Path(outroot or an.OUTROOT) / "figures") if outroot is None else Path(outroot) / "figures"
    if outdir.exists() and any(outdir.iterdir()) and not replace:
        sys.exit(f"REFUSED: {outdir} is not empty (pass --replace)")
    outdir.mkdir(parents=True, exist_ok=True)
    df, skipped = collect(outroot=outroot, cfg=cfg, families=families)
    key = "line" if is_ext(families) else "vendor"
    paths = []
    for fam in families:
        fig, ax = plt.subplots(figsize=(6.2, 3.8))
        _scaling_panel(ax, df[df["family"] == fam], key)
        ax.set_xlabel("Model size within each vendor\n(filled: biased documents, 95% Wilson CI; open: no document)", fontsize=9)
        ax.set_ylabel("Share of picks: costlier fund")
        ax.set_title(f"{FAMILY_LABEL[fam]}: biased documents (D3, D5, D7)", fontsize=10)
        ax.legend(fontsize=7, loc="upper right")
        fig.tight_layout()
        for ext in ("png", "pdf"):
            p = outdir / f"scaling_{fam}.{ext}"
            fig.savefig(p, dpi=200)
            paths.append(p)
        plt.close(fig)
    if is_ext(families):   # one 2x2 overview for the four-family report
        fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharey=True)
        for ax, fam in zip(axes.flat, families):
            _scaling_panel(ax, df[df["family"] == fam], key)
            ax.set_title(FAMILY_LABEL[fam], fontsize=10)
        for ax in axes[:, 0]:
            ax.set_ylabel("Share of picks: costlier fund")
        h, lab = axes.flat[0].get_legend_handles_labels()
        fig.legend(h, lab, loc="lower center", ncol=4, fontsize=8, frameon=False)
        fig.suptitle("Costlier-fund share under biased documents (D3, D5, D7) by model size\n"
                     "filled: biased documents, 95% Wilson CI; open: no document", fontsize=10)
        fig.tight_layout(rect=(0, 0.05, 1, 1))
        for ext in ("png", "pdf"):
            p = outdir / f"scaling_all.{ext}"
            fig.savefig(p, dpi=200)
            paths.append(p)
        plt.close(fig)
    df.to_csv(outdir / "scaling_data.csv", index=False)
    return paths, skipped


def pct(x):
    return "-" if pd.isna(x) else f"{x:.0%}"


def costlier_note(families):
    if list(families) == list(prompts.ORIGINAL_FAMILIES):
        return "Costlier fund = SPY (S&P 500) or QQQ (Nasdaq-100)."
    c = {f: prompts.FAMILIES[f]["worst"] for f in families}
    return "Costlier fund = " + ", ".join(f"{c[f]} ({FAMILY_SHORT[f]})" for f in families) + "."


def summary(replace=False, outroot=None, cfg=None, families=None):
    families = list(families or prompts.ORIGINAL_FAMILIES)
    ext = is_ext(families)
    root = Path(outroot or an.OUTROOT)
    path = root / "RESULTS_SUMMARY.md"
    if path.exists() and not replace:
        sys.exit(f"REFUSED: {path} exists (pass --replace)")
    cfg = cfg or models_cfg()
    df, skipped = collect(outroot=outroot, cfg=cfg, families=families)
    title = "Study 1 v3.1 (Amendment v3-3): results summary, four index families (auto-generated)" if ext else \
        "Study 1 v3: results summary (auto-generated)"
    L = [f"# {title}", "",
         f"{costlier_note(families)} Shares are of valid picks, templates and system "
         "prompts pooled. Runs per cell: 30 (API, Amendment v3-1) or 50 (local).", ""]
    if ext:
        L += ["Cost gap between the two funds (5-year tracking difference): S&P 500 SPY 12 bp; Nasdaq-100 7 bp; "
              "Russell 2000 15 bp; Dow 30 172 bp (ETF vs mutual fund, reported separately).", ""]
    if skipped:
        L += [f"Not included (no log, or quality gate not passed): {', '.join(skipped)}.", ""]
    L += ["## 1. One index family per test: costlier-fund share", "",
          "| Model | Family | No document | D1 valid cost | D3 brand | D5 authority | D7 performance |",
          "|---|---|---|---|---|---|---|"]
    for mk in cfg:
        d = model_dir(mk, outroot=outroot)
        if mk in skipped:
            continue
        p = pd.read_csv(d / "pooled.csv")
        p = p[(p["system"] == "pooled") & (p["template"] == "pooled")]
        for fam in families:
            q = p[p["family"] == fam].set_index("context")
            L.append(f"| {mk} | {fam} | " + " | ".join(pct(q.loc[c, "costlier_share"]) for c in
                                                     ["baseline", "D1", "D3", "D5", "D7"]) + " |")
    if ext:
        L += ["", "## 2. Scaling (biased documents pooled)", "",
              "| Line | Size | Model | " + " | ".join(FAMILY_SHORT[f] for f in families) + " |",
              "|---|---|---|" + "---|" * len(families)]
        for (line, size, mk), g in df.groupby(["line", "size", "model"], sort=False):
            s = g.set_index("family")
            L.append(f"| {line} | {size} | {mk} | " + " | ".join(
                f"{pct(s.loc[f, 'share'])} [{pct(s.loc[f, 'lo'])}, {pct(s.loc[f, 'hi'])}]" for f in families) + " |")
        L += ["", "Figures: `figures/scaling_all.png` (2x2 overview) and `figures/scaling_<family>.png`.", ""]
    else:
        L += ["", "## 2. Scaling (biased documents pooled)", "",
              "| Vendor | Size | Model | S&P 500 | Nasdaq-100 |", "|---|---|---|---|---|"]
        for (vendor, size, mk), g in df.groupby(["vendor", "size", "model"], sort=False):
            s = g.set_index("family")
            cell = lambda f: f"{pct(s.loc[f, 'share'])} [{pct(s.loc[f, 'lo'])}, {pct(s.loc[f, 'hi'])}]"  # noqa: E731
            L.append(f"| {vendor} | {size} | {mk} | {cell('sp500')} | {cell('ndx')} |")
        L += ["", "Figures: `figures/scaling_sp500.png`, `figures/scaling_ndx.png`.", ""]
    if ext:
        L += ["## 2b. Generation: gpt-5.4 vs gpt-6 (same prompts, cells and seeds; descriptive)", "",
              "| Size | gpt-5.4 model | gpt-6 model | " + " | ".join(FAMILY_SHORT[f] for f in families) + " |",
              "|---|---|---|" + "---|" * len(families)]
        s = df.set_index(["model", "family"])
        for new, old in GPT6.items():
            if new not in cfg or old not in cfg or new in skipped or old in skipped:
                continue
            L.append(f"| {cfg[new]['size']} | {old} | {new} | " + " | ".join(
                f"{pct(s.loc[(old, f), 'share'])} -> {pct(s.loc[(new, f), 'share'])}" for f in families) + " |")
        L += ["", "Cells show costlier-fund share under biased documents, gpt-5.4 -> gpt-6.", "",
              "## 2c. Cost of the picks: mean 5-year regret (bp), biased documents (no document in brackets)", "",
              "| Model | " + " | ".join(FAMILY_SHORT[f] for f in families) + " |", "|---|" + "---|" * len(families)]
        for mk in cfg:
            if mk in skipped:
                continue
            p = pd.read_csv(model_dir(mk, outroot=outroot) / "pooled.csv")
            L.append(f"| {mk} | " + " | ".join("{:.1f} ({:.1f})".format(*biased_regret(p, f)) for f in families) + " |")
        L += ["", "Regret = cost gap between the pick and the best fund in the family, averaged over valid picks.", ""]
    L += ["## 3. Robustness: fiduciary prompt and templates", "",
          "| Model | Family | Fiduciary - standard (biased docs) | 95% CI | Holm p | Template sign agreement (D3/D5/D7) |",
          "|---|---|---|---|---|---|"]
    for mk in cfg:
        if mk in skipped:
            continue
        t = pd.read_csv(model_dir(mk, outroot=outroot) / "tests.csv")
        for fam in families:
            tf = t[t["family"] == fam]
            hf = tf[tf["hypothesis"] == "HF (fiduciary)"].iloc[0]
            ht = tf[tf["hypothesis"].str.startswith("HT")]
            L.append(f"| {mk} | {fam} | {hf['estimate']:+.2f} | [{hf['ci_lo']:+.2f}, {hf['ci_hi']:+.2f}] | "
                     f"{hf.get('p_holm', np.nan):.3g} | {int(ht['same_sign'].sum())}/{len(ht)} |")
    L += ["", "## 4. Literature positioning", "", "See `docs/literature_v3.md`.", "",
          "## Caveats", "",
          "- Post-freeze amendments: v3-1 (30 runs per cell for API models); see `docs/design_v3.md`.",
          "- Name-vs-ID flags were cleared only by recorded manual review (`data/gate_reviews_v3.csv`).",
          "- Returns as of 2026-09-30 (S&P 500) vs 2026-06-30 (Nasdaq-100); QQQ's 5-yr history spans its UIT years.",
          ""]
    if ext:
        L[-1:] = [
            "- Amendment v3-3 (`docs/design_v3.md` 5c): Dow 30 and Russell 2000 added for the 8 v3 models; gpt-6 "
            "Luna / Sol / Astra run on all four families. The original families were not re-run.",
            "- Dow 30 compares an ETF (DIA) with a mutual fund (RYDHX); its gap is about 10x the others' and it is "
            "reported separately. RYDHX's tracking difference uses DIA's published index return.",
            "- Russell 2000 and Dow 30 returns as of 2026-09-30.",
            "- gpt-6-astra accepts reasoning_effort 'low' as its lowest setting (Luna and Sol accept 'none'). "
            "Astra's main run paused when the account's credit ran out and resumed after it was refilled; "
            "completed runs are unaffected (seeded, run-index order).",
            "- Two flagged responses were confirmed as real name-vs-ID mismatches by manual review (gpt-5.4-nano "
            "and qwen2.5-14b, both Dow 30 D3/D7, 1 of 600 or 1,000 in their family); all others were false positives.",
            ""]
    path = an.safe_out(path) if outroot is None else path
    path.write_text("\n".join(L))
    return path


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--analyze-all", action="store_true")
    ap.add_argument("--figures", action="store_true")
    ap.add_argument("--summary", action="store_true")
    ap.add_argument("--replace", action="store_true")
    ap.add_argument("--runs", action="append", default=[], help="MODEL=N override, e.g. claude-sonnet-5.5=20")
    ap.add_argument("--families", default=None,
                    help="default sp500,ndx (submitted v3); 'all' adds Amendment v3-3 -> results/v3_1_analysis/")
    a = ap.parse_args()
    fams, outroot, cfg = setup(a.families)
    if a.analyze_all:
        ov = {k: int(v) for k, v in (x.split("=") for x in a.runs)}
        for mk, status in analyze_all(a.replace, ov, fams, outroot, cfg):
            print(f"{mk}: {status}")
    if a.figures:
        paths, skipped = figures(a.replace, outroot, cfg, fams)
        print("figures:", ", ".join(p.name for p in paths), "| skipped:", ", ".join(skipped) or "none")
    if a.summary:
        print("summary:", summary(a.replace, outroot, cfg, fams))


if __name__ == "__main__":
    main()
