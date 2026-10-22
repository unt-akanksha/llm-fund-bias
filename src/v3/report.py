"""Study 1 v3 reporting: run all analyses, the scaling figure, and the auto-filled results summary.

  python src/v3/report.py --analyze-all [--runs claude-sonnet-5.5=20] [--replace]
        each model with a log: main analysis (own run count) and matched comparison (runs 0-29)
  python src/v3/report.py --figures [--replace]       results/v3_analysis/figures/scaling_<family>.png/.pdf
  python src/v3/report.py --summary [--replace]       results/v3_analysis/RESULTS_SUMMARY.md

Reads only the analysis outputs (pooled.csv, tests.csv, gate.txt); writes only under results/v3_analysis/.
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
                "ollama": "Qwen 2.5 local (7B / 14B)"}
FAMILY_LABEL = {"sp500": "S&P 500 (SPY vs IVV vs VOO)", "ndx": "Nasdaq-100 (QQQ vs QQQM)"}


def models_cfg():
    return yaml.safe_load(open(ROOT / "config" / "models_v3.yaml"))["models"]


def model_dir(mk, matched=False, outroot=None):
    root = Path(outroot or an.OUTROOT)
    return root / "matched30" / mk if matched else root / mk


def analyze_all(replace=False, runs_override=None):
    runs_override = runs_override or {}
    out = []
    for mk in models_cfg():
        if not (an.LOGDIR / f"main_{mk}.jsonl").exists():
            out.append((mk, "no log"))
            continue
        runs = runs_override.get(mk)
        ok, d, unrev = an.analyze(mk, replace=replace, runs=runs)
        ok30, _, _ = an.analyze(mk, replace=replace, out=model_dir(mk, matched=True), runs=30)
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


def gate_passed(d):
    g = d / "gate.txt"
    return g.exists() and "GATE (after manual review): PASS" in g.read_text() and (d / "pooled.csv").exists()


def collect(matched=False, outroot=None, cfg=None):
    cfg = cfg or models_cfg()
    rows, skipped = [], []
    for mk, m in cfg.items():
        d = model_dir(mk, matched, outroot)
        if not gate_passed(d):
            skipped.append(mk)
            continue
        pooled = pd.read_csv(d / "pooled.csv")
        for fam in prompts.FAMILIES:
            rows.append({"model": mk, "vendor": m["provider"], "size": m.get("size"), "family": fam,
                         **biased_share(pooled, fam)})
    return pd.DataFrame(rows), skipped


def figures(replace=False, outroot=None, cfg=None):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    outdir = an.safe_out(Path(outroot or an.OUTROOT) / "figures") if outroot is None else Path(outroot) / "figures"
    if outdir.exists() and any(outdir.iterdir()) and not replace:
        sys.exit(f"REFUSED: {outdir} is not empty (pass --replace)")
    outdir.mkdir(parents=True, exist_ok=True)
    df, skipped = collect(outroot=outroot, cfg=cfg)
    paths = []
    for fam in prompts.FAMILIES:
        fig, ax = plt.subplots(figsize=(6.2, 3.8))
        d = df[df["family"] == fam]
        for j, (vendor, g) in enumerate(d.groupby("vendor", sort=False)):
            g = g.assign(x=g["size"].map({s: i for i, s in enumerate(SIZES)})).sort_values("x")
            off = (j - 1) * 0.08
            eb = ax.errorbar(g["x"] + off, g["share"], yerr=[(g["share"] - g["lo"]).clip(lower=0), (g["hi"] - g["share"]).clip(lower=0)], marker="o",
                             capsize=3, label=VENDOR_LABEL.get(vendor, vendor))
            ax.scatter(g["x"] + off, g["baseline_share"], marker="o", s=36, facecolors="none",
                       edgecolors=eb[0].get_color(), linewidths=1.2, zorder=3)
        ax.set_xticks(range(len(SIZES)), ["small", "mid", "large"])
        ax.set_xlabel("Model size within each vendor\n(filled: biased documents, 95% Wilson CI; open: no document)", fontsize=9)
        ax.set_ylim(-0.03, 1.03)
        ax.set_ylabel("Share of picks: costlier fund")
        ax.set_title(f"{FAMILY_LABEL[fam]}: biased documents (D3, D5, D7)", fontsize=10)
        ax.legend(fontsize=7, loc="upper right")
        fig.tight_layout()
        for ext in ("png", "pdf"):
            p = outdir / f"scaling_{fam}.{ext}"
            fig.savefig(p, dpi=200)
            paths.append(p)
        plt.close(fig)
    df.to_csv(outdir / "scaling_data.csv", index=False)
    return paths, skipped


def pct(x):
    return "-" if pd.isna(x) else f"{x:.0%}"


def summary(replace=False, outroot=None, cfg=None):
    root = Path(outroot or an.OUTROOT)
    path = root / "RESULTS_SUMMARY.md"
    if path.exists() and not replace:
        sys.exit(f"REFUSED: {path} exists (pass --replace)")
    cfg = cfg or models_cfg()
    df, skipped = collect(outroot=outroot, cfg=cfg)
    L = ["# Study 1 v3: results summary (auto-generated)", "",
         "Costlier fund = SPY (S&P 500) or QQQ (Nasdaq-100). Shares are of valid picks, templates and system "
         "prompts pooled. Runs per cell: 30 (API, Amendment v3-1) or 50 (local).", ""]
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
        for fam in prompts.FAMILIES:
            q = p[p["family"] == fam].set_index("context")
            L.append(f"| {mk} | {fam} | " + " | ".join(pct(q.loc[c, "costlier_share"]) for c in
                                                     ["baseline", "D1", "D3", "D5", "D7"]) + " |")
    L += ["", "## 2. Scaling (biased documents pooled)", "",
          "| Vendor | Size | Model | S&P 500 | Nasdaq-100 |", "|---|---|---|---|---|"]
    for (vendor, size, mk), g in df.groupby(["vendor", "size", "model"], sort=False):
        s = g.set_index("family")
        cell = lambda f: f"{pct(s.loc[f, 'share'])} [{pct(s.loc[f, 'lo'])}, {pct(s.loc[f, 'hi'])}]"  # noqa: E731
        L.append(f"| {vendor} | {size} | {mk} | {cell('sp500')} | {cell('ndx')} |")
    L += ["", "Figures: `figures/scaling_sp500.png`, `figures/scaling_ndx.png`.", "",
          "## 3. Robustness: fiduciary prompt and templates", "",
          "| Model | Family | Fiduciary - standard (biased docs) | 95% CI | Holm p | Template sign agreement (D3/D5/D7) |",
          "|---|---|---|---|---|---|"]
    for mk in cfg:
        if mk in skipped:
            continue
        t = pd.read_csv(model_dir(mk, outroot=outroot) / "tests.csv")
        for fam in prompts.FAMILIES:
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
    a = ap.parse_args()
    if a.analyze_all:
        ov = {k: int(v) for k, v in (x.split("=") for x in a.runs)}
        for mk, status in analyze_all(a.replace, ov):
            print(f"{mk}: {status}")
    if a.figures:
        paths, skipped = figures(a.replace)
        print("figures:", ", ".join(p.name for p in paths), "| skipped:", ", ".join(skipped) or "none")
    if a.summary:
        print("summary:", summary(a.replace))


if __name__ == "__main__":
    main()
