"""Analyze runs/clean.csv: rates, choice distributions, Gini, shifts vs baseline, position bias, order.

  python src/analyze.py                 # main  -> results/tables, results/figures
  python src/analyze.py --phase pilot   # pilot -> results/pilot/tables, results/pilot/figures
"""

import argparse
import warnings

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy.stats import chi2_contingency, chisquare, fisher_exact
from statsmodels.stats.proportion import proportion_confint

from common import ROOT, load_conditions

MEASURES = {"chose_f1": "F1 rate", "chose_f2": "F2 rate", "chose_low_fee": "Low-fee rate"}
FUNDS = [f"F{i}" for i in range(1, 9)]

# Chart style: reference palette (dataviz skill), light mode. Color follows the fund, never its rank.
FUND_COLORS = dict(zip(FUNDS, ["#2a78d6", "#eb6834", "#1baf7a", "#eda100",
                               "#e87ba4", "#008300", "#6250d6", "#e34948"]))
INK, INK2, MUTED, GRID, AXIS, SURFACE = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#c3c2b7", "#fcfcfb"
plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
    "font.size": 9, "text.color": INK, "axes.labelcolor": INK2, "axes.edgecolor": AXIS,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "axes.grid.axis": "y", "grid.color": GRID, "grid.linewidth": 0.6,
    "axes.axisbelow": True, "axes.titlesize": 10, "axes.titleweight": "bold",
})


# ---------- metrics ----------

def wilson(k, n):
    lo, hi = proportion_confint(k, n, method="wilson") if n else (np.nan, np.nan)
    return lo, hi


def gini(counts):
    """Gini index of choice counts across funds (Zhi et al.): 0 = picks spread evenly over all funds,
    (n-1)/n = every pick on one fund (0.875 for 8 funds). Zero-count funds are included."""
    x = np.asarray(counts, dtype=float)
    if x.sum() == 0:
        return np.nan
    n = len(x)
    return np.abs(x[:, None] - x[None, :]).sum() / (2 * n * n * x.mean())


def rates_table(df):
    rows = []
    for (mk, cond), g in df.groupby(["model_key", "condition_id"], sort=False):
        row = {"model_key": mk, "condition_id": cond, "n": len(g)}
        for col, label in MEASURES.items():
            k = int(g[col].sum())
            lo, hi = wilson(k, len(g))
            key = col.removeprefix("chose_")
            row.update({f"{key}_k": k, f"{key}_rate": k / len(g), f"{key}_lo": lo, f"{key}_hi": hi})
        counts = g.chosen_fund.value_counts().reindex(FUNDS, fill_value=0)
        row["gini"] = gini(counts)
        row["gini_normalized"] = row["gini"] * len(FUNDS) / (len(FUNDS) - 1)  # rescaled to 0..1
        rows.append(row)
    return pd.DataFrame(rows)


def distribution_table(df):
    d = (df.groupby(["model_key", "condition_id"], sort=False).chosen_fund.value_counts()
         .unstack(fill_value=0).reindex(columns=FUNDS, fill_value=0))
    shares = d.div(d.sum(axis=1), axis=0)
    out = d.add_suffix("_n").join(shares.add_suffix("_share"))
    return out.reset_index()


def lpm(df, formula):
    """OLS linear probability model with HC3 robust SEs. Returns None if the outcome has no variation."""
    y = formula.split("~")[0].strip()
    if df[y].nunique() < 2:
        return None
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        return smf.ols(formula, data=df).fit(cov_type="HC3")


def shifts_table(df):
    """Percentage-point shift of each measure vs baseline (LPM, HC3), plus chi-square / Fisher tests."""
    rows = []
    for mk, g in df.groupby("model_key", sort=False):
        if "baseline" not in set(g.condition_id) or g.condition_id.nunique() < 2:
            continue
        base = g[g.condition_id == "baseline"]
        for col in MEASURES:
            fit = lpm(g, f"{col} ~ C(condition_id, Treatment('baseline'))")
            for cond in [c for c in g.condition_id.unique() if c != "baseline"]:
                term = f"C(condition_id, Treatment('baseline'))[T.{cond}]"
                treat = g[g.condition_id == cond]
                row = {"model_key": mk, "condition_id": cond, "measure": col.removeprefix("chose_"),
                       "baseline_rate": base[col].mean(), "condition_rate": treat[col].mean(),
                       "n_baseline": len(base), "n_condition": len(treat)}
                if fit is not None and term in fit.params:
                    lo, hi = fit.conf_int().loc[term]
                    row.update({"shift_pp": 100 * fit.params[term], "ci_lo_pp": 100 * lo,
                                "ci_hi_pp": 100 * hi, "p_hc3": fit.pvalues[term]})
                # 2x2 test on the binary measure
                table = np.array([[treat[col].sum(), len(treat) - treat[col].sum()],
                                  [base[col].sum(), len(base) - base[col].sum()]])
                if (table.sum(axis=0) > 0).all():
                    row["p_chi2_2x2"] = chi2_contingency(table)[1]
                row["p_fisher_2x2"] = fisher_exact(table)[1]
                # Full choice distribution (funds picked at least once in either group)
                if col == "chose_f1":
                    ct = pd.crosstab(pd.concat([base, treat]).condition_id, pd.concat([base, treat]).chosen_fund)
                    if ct.shape[1] > 1:
                        chi = chi2_contingency(ct)
                        row["p_chi2_distribution"] = chi[1]
                        row["min_expected_count"] = chi[3].min()  # <5 => interpret with caution
                rows.append(row)
    return pd.DataFrame(rows)


def position_tables(df):
    """Row-position bias: pick share by row (vs uniform), and F1 rate by F1's row."""
    pick_rows, f1_rows, tests = [], [], []
    for scope, d in [("baseline", df[df.condition_id == "baseline"]), ("all_conditions", df)]:
        for mk, g in d.groupby("model_key", sort=False):
            if g.empty:
                continue
            counts = g.chosen_position.value_counts().reindex(range(1, 9), fill_value=0)
            for pos, k in counts.items():
                pick_rows.append({"model_key": mk, "scope": scope, "row_position": pos,
                                  "n_picked": int(k), "share": k / len(g)})
            f1 = g.groupby("dominant_position").chose_f1.agg(["mean", "count"]).reindex(range(1, 9))
            for pos, r in f1.iterrows():
                f1_rows.append({"model_key": mk, "scope": scope, "f1_row_position": pos,
                                "n": r["count"], "f1_rate": r["mean"]})
            fit = lpm(g, "chose_f1 ~ dominant_position")
            tests.append({
                "model_key": mk, "scope": scope, "n": len(g),
                "p_chi2_picks_uniform": chisquare(counts).pvalue,
                "share_first_row": counts[1] / len(g), "share_last_row": counts[8] / len(g),
                "f1_rate_slope_per_row_pp": 100 * fit.params["dominant_position"] if fit else np.nan,
                "p_slope_hc3": fit.pvalues["dominant_position"] if fit else np.nan,
            })
    return pd.DataFrame(pick_rows), pd.DataFrame(f1_rows), pd.DataFrame(tests)


def order_table(df):
    """Order effects: (a) fixed-order conditions ord_*; (b) ratings-source position within shuffled src_all."""
    rows = []
    for mk, g in df.groupby("model_key", sort=False):
        ordc = g[g.condition_id.str.startswith("ord_")]
        if ordc.condition_id.nunique() > 1:
            ct = pd.crosstab(ordc.condition_id, ordc.chose_f1)
            row = {"model_key": mk, "test": "fixed_order_conditions", "n": len(ordc),
                   "groups": ";".join(f"{c}={ordc[ordc.condition_id == c].chose_f1.mean():.3f}"
                                      for c in sorted(ordc.condition_id.unique()))}
            if ct.shape[1] > 1:
                row["p_chi2_f1"] = chi2_contingency(ct)[1]
            rows.append(row)
        sa = g[(g.condition_id == "src_all") & g.ratings_position.notna()]
        if sa.ratings_position.nunique() > 1:
            fit = lpm(sa, "chose_f1 ~ C(ratings_position, Treatment(1))")
            row = {"model_key": mk, "test": "src_all_ratings_position", "n": len(sa),
                   "groups": ";".join(f"pos{int(p)}={sa[sa.ratings_position == p].chose_f1.mean():.3f}"
                                      for p in sorted(sa.ratings_position.unique()))}
            if fit is not None:
                terms = [t for t in fit.params.index if t.startswith("C(")]
                row["p_wald_joint_hc3"] = float(fit.f_test(", ".join(f"{t} = 0" for t in terms)).pvalue)
                row["linear_slope_pp"] = 100 * lpm(sa, "chose_f1 ~ ratings_position").params["ratings_position"]
            rows.append(row)
    return pd.DataFrame(rows)


# ---------- figures ----------

def fig_f1_rates(rates, cond_order, path):
    models = list(rates.model_key.unique())
    fig, axes = plt.subplots(1, len(models), figsize=(max(4.5, 0.6 * len(cond_order) + 1.5) * len(models), 3.6),
                             sharey=True, squeeze=False)
    for ax, mk in zip(axes[0], models):
        r = rates[rates.model_key == mk].set_index("condition_id").reindex(
            [c for c in cond_order if c in set(rates[rates.model_key == mk].condition_id)])
        x = np.arange(len(r))
        err = np.vstack([r.f1_rate - r.f1_lo, r.f1_hi - r.f1_rate]) * 100
        ax.bar(x, r.f1_rate * 100, width=0.55, color=FUND_COLORS["F1"], edgecolor=SURFACE, linewidth=1)
        ax.errorbar(x, r.f1_rate * 100, yerr=err, fmt="none", ecolor=INK2, elinewidth=1, capsize=3)
        if "baseline" in r.index and len(r) > 1:
            ax.axhline(r.loc["baseline", "f1_rate"] * 100, color=MUTED, linestyle="--", linewidth=1)
        for xi, v, n in zip(x, r.f1_rate * 100, r.n):
            ax.text(xi, 2, f"{v:.0f}%", ha="center", va="bottom", color=SURFACE, fontsize=8, fontweight="bold")
        ax.set_xticks(x, r.index, rotation=35, ha="right")
        ax.set_xlim(-0.7, max(len(r), 4) - 0.3)  # keep bars thin even with few conditions
        ax.set_ylim(0, 100)
        ax.set_title(f"{mk}  (n={int(r.n.iloc[0])}/condition)" if r.n.nunique() == 1 else mk, loc="left")
    axes[0][0].set_ylabel("Picks of F1, the dominant fund (%)")
    fig.suptitle("F1 pick rate by condition, with 95% Wilson CIs", x=0.01, ha="left", fontsize=11, fontweight="bold")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


def fig_distribution(dist, cond_order, path):
    models = list(dist.model_key.unique())
    n_cond = dist.condition_id.nunique()
    fig, axes = plt.subplots(len(models), 1, figsize=(7.5, 0.45 * n_cond * len(models) + 1.6),
                             squeeze=False, sharex=True)
    for ax, mk in zip(axes[:, 0], models):
        d = dist[dist.model_key == mk].set_index("condition_id")
        d = d.reindex([c for c in cond_order if c in d.index][::-1])
        left = np.zeros(len(d))
        for f in FUNDS:
            v = d[f"{f}_share"].values * 100
            ax.barh(d.index, v, left=left, color=FUND_COLORS[f], edgecolor=SURFACE, linewidth=1.2, height=0.6,
                    label=f)
            for yi, (l, w) in enumerate(zip(left, v)):
                if w >= 8:  # selective direct labels: only segments wide enough to hold one
                    ax.text(l + w / 2, yi, f"{f} {w:.0f}%", ha="center", va="center", fontsize=7, color=SURFACE)
            left += v
        ax.set_xlim(0, 100)
        ax.grid(axis="y", visible=False)
        ax.grid(axis="x", visible=True)
        ax.set_title(mk, loc="left")
    axes[-1, 0].set_xlabel("Share of picks (%)")
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, ncol=8, loc="upper left", bbox_to_anchor=(0.01, 0.995), frameon=False,
               fontsize=8, handlelength=1, columnspacing=1)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    fig.savefig(path, dpi=200)
    plt.close(fig)


def fig_position(picks, path):
    p = picks[picks.scope == "baseline"]
    models = list(p.model_key.unique())
    if not models:
        return
    fig, axes = plt.subplots(1, len(models), figsize=(4 * len(models), 3.2), sharey=True, squeeze=False)
    for ax, mk in zip(axes[0], models):
        r = p[p.model_key == mk]
        ax.bar(r.row_position, r.share * 100, width=0.6, color=FUND_COLORS["F1"], edgecolor=SURFACE)
        ax.axhline(100 / 8, color=MUTED, linestyle="--", linewidth=1)
        ax.text(8.4, 100 / 8, "uniform", va="bottom", ha="right", color=MUTED, fontsize=7)
        ax.set_xticks(range(1, 9))
        ax.set_xlabel("Row position of chosen fund (1 = top)")
        ax.set_title(f"{mk}  (baseline, n={int(r.n_picked.sum())})", loc="left")
    axes[0][0].set_ylabel("Share of picks (%)")
    fig.tight_layout()
    fig.savefig(path, dpi=200)
    plt.close(fig)


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase", default="main")
    phase = ap.parse_args().phase
    clean_path = ROOT / "runs" / ("clean.csv" if phase == "main" else f"clean_{phase}.csv")
    out = ROOT / "results" / ("" if phase == "main" else phase)
    (out / "tables").mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(clean_path)
    cond_order = [c for c in load_conditions().condition_id if c in set(df.condition_id)]
    df["condition_id"] = pd.Categorical(df.condition_id, cond_order, ordered=True)
    df = df.sort_values(["model_key", "condition_id"])
    df["condition_id"] = df.condition_id.astype(str)

    rates = rates_table(df)
    dist = distribution_table(df)
    shifts = shifts_table(df)
    picks, f1pos, postests = position_tables(df)
    order = order_table(df)

    tables = {"rates": rates, "choice_distribution": dist, "shifts_vs_baseline": shifts,
              "position_picks": picks, "position_f1_rate": f1pos, "position_tests": postests,
              "order_tests": order}
    for name, t in tables.items():
        if not t.empty:
            t.round(4).to_csv(out / "tables" / f"{name}.csv", index=False)

    fig_f1_rates(rates, cond_order, out / "figures" / "f1_rate_by_condition.png")
    fig_distribution(dist, cond_order, out / "figures" / "choice_distribution.png")
    fig_position(picks, out / "figures" / "position_bias.png")

    pd.set_option("display.width", 160)
    print("Rates (with 95% Wilson CIs):")
    print(rates[["model_key", "condition_id", "n", "f1_rate", "f1_lo", "f1_hi", "f2_rate", "low_fee_rate",
                 "gini"]].round(3).to_string(index=False))
    if not shifts.empty:
        print("\nF1 shift vs baseline (pp, LPM HC3):")
        s = shifts[shifts.measure == "f1"]
        print(s[["model_key", "condition_id", "shift_pp", "ci_lo_pp", "ci_hi_pp", "p_hc3", "p_fisher_2x2"]]
              .round(3).to_string(index=False))
    print("\nPosition tests:")
    print(postests.round(3).to_string(index=False))
    if not order.empty:
        print("\nOrder tests:")
        print(order.round(3).to_string(index=False))
    print(f"\nTables -> {(out / 'tables').relative_to(ROOT)}   Figures -> {(out / 'figures').relative_to(ROOT)}")


if __name__ == "__main__":
    main()
