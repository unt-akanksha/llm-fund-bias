"""Post-hoc robustness check: does the fund NAMED in the reasoning match the fund ID the model output?

  python src/name_id_check.py     # reads runs/clean.csv -> results/tables/name_id_*.csv

Added after the main analysis, following a review that found qwen ord_FRA "F2" picks whose reasoning
recommends the Alder fund (F1). Reads only runs/clean.csv; raw logs and existing tables are untouched.

How "recommended" is decided (rule-based, in this order; the rule used is logged as `basis`):
  1. no_name   - no fund name or ID in the reasoning -> not classifiable (excluded from mismatch rates).
  2. single    - exactly one distinct fund named -> that fund.
  3. explicit  - a selection verb directly names a fund ("I chose the F2 ...", "we recommend the Alder ...",
                 "the Alder ... is selected") and points to exactly one fund -> that fund.
  4. contrast  - otherwise (several funds named), drop mentions that are only compared or rejected:
                   * in a concessive clause ("While/Although/Unlike/Despite X ...", up to the comma),
                   * after a comparison word in the same clause ("than", "like", "as", "to", "of", "with",
                     "between", "in"), e.g. "same index as the Birch ...",
                   * when the rest of the sentence criticizes it ("..., but its fee ...", "too", "despite",
                     "may not", ...),
                   * hedged mentions ("could also consider X").
                 If one fund remains -> that fund. If several remain: with a pivot sentence ("However",
                 "In contrast", "on the other hand", "Therefore"), the fund named at or after the last pivot;
                 with no pivot, the one fund said to "stand out" / be "a solid choice".
                 These cues only choose AMONG several named funds. They never overrule a lone name: on
                 single-name runs they fire mostly on endorsements ("X stands out, despite a higher fee").
  5. ambiguous - anything else -> not classifiable.
"""

import re

import pandas as pd
from scipy.stats import chi2_contingency
from statsmodels.stats.proportion import proportion_confint

from build_clean import fund_flags
from common import DATA, ROOT, load_grid

TABLES = ROOT / "results" / "tables"

SELECT_VERB = r"(?:chose|choose|choosing|chosen|select|selected|selecting|recommend|recommending|opt for|pick|picked)"
CONCESSIVE = re.compile(r"^\s*(?:while|although|though|unlike|despite|compared)\b", re.I)
COMPARISON = re.compile(r"\b(?:than|like|as|to|of|with|between|in)\s+(?:the\s+)?$", re.I)
NEGATIVE = re.compile(r"\b(?:but (?:its|their|it|they)|too|despite|may not|might not|not suitable|less attractive)\b", re.I)
STRONG = re.compile(r"[^,.]{0,45}?\b(?:stands? out|is the best|is an? (?:solid|excellent|strong|ideal) choice)", re.I)
HEDGE = re.compile(r"\bcould also consider\s+(?:the\s+)?$", re.I)
PIVOT = re.compile(r"^\s*(?:however|in contrast|therefore|on the other hand)\b|\bon the other hand\b", re.I)


def name_map(grid=None):
    """{'Alder': 'F1', ...}: the first word of each fund name is unique in the grid."""
    grid = load_grid() if grid is None else grid
    return {r.name.split()[0]: r.fund_id for r in grid.itertuples()}


def _mentions(text, names):
    """[(start, end, fund_id)] for every fund name (capitalized, whole word) or ID token like 'F3'."""
    out = []
    for word, fid in names.items():
        out += [(m.start(), m.end(), fid) for m in re.finditer(rf"\b{word}(?:es|s|'s)?\b", text)]  # "Birches"
    ids = set(names.values())
    out += [(m.start(), m.end(), f"F{m.group(1)}") for m in re.finditer(r"\bF([1-9])\b", text)
            if f"F{m.group(1)}" in ids]
    return sorted(out)


def _sentences(text):
    text = text.replace("U.S.", "US")
    spans, start = [], 0
    for m in re.finditer(r"[.!?](?=\s+[A-Z(]|\s*$)", text):
        spans.append((start, m.end()))
        start = m.end()
    if start < len(text):
        spans.append((start, len(text)))
    return text, spans


def recommended_fund(text, names):
    """Return (fund_id or None, basis). See module docstring for the rules."""
    if not isinstance(text, str) or not text.strip():
        return None, "no_name"
    text, sents = _sentences(text)
    ments = _mentions(text, names)
    funds = {f for _, _, f in ments}
    if not funds:
        return None, "no_name"
    if len(funds) == 1:
        return funds.pop(), "single"

    # 3. explicit selection: verb ... fund (no sentence break, <= 40 chars between), or "fund ... is selected"
    explicit = set()
    for s, e, f in ments:
        before = text[max(0, s - 40):s]
        if re.search(rf"\b{SELECT_VERB}\b(?:(?!\.\s|,).)*$", before, re.I) and not CONCESSIVE.search(before):
            explicit.add(f)
        if re.match(r"[^.,]{0,40}?\bis\s+(?:selected|chosen|recommended)\b", text[e:e + 60], re.I):
            explicit.add(f)
    if len(explicit) == 1:
        return explicit.pop(), "explicit"

    # 4. drop compared / rejected / hedged mentions
    kept = []  # (sentence_index, start, end, fund_id)
    for s, e, f in ments:
        si = next(i for i, (a, b) in enumerate(sents) if a <= s < b)
        a, b = sents[si]
        cstart = max(a, text.rfind(",", a, s) + 1)
        cend = text.find(",", e, b)
        clause = text[cstart:b if cend == -1 else cend]
        if CONCESSIVE.search(clause) or COMPARISON.search(text[cstart:s]) or HEDGE.search(text[a:s]):
            continue
        if NEGATIVE.search(text[e:b]):  # "X offers strong returns, but its fee ..." criticizes X
            continue
        kept.append((si, s, e, f))
    remaining = {k[3] for k in kept}
    if len(remaining) == 1:
        return remaining.pop(), "contrast"
    if len(remaining) > 1:
        # a pivot sentence ("However, ...") and anything after it carries the final choice
        pivots = [i for i, (a, b) in enumerate(sents) if PIVOT.search(text[a:b])]
        if pivots:
            last = {k[3] for k in kept if k[0] >= pivots[-1]}
            if len(last) == 1:
                return last.pop(), "contrast"
        else:
            # no pivot: the one fund described as standing out / being the choice
            praised = {f for si, s, e, f in kept if STRONG.match(text[e:sents[si][1]])}
            if len(praised) == 1:
                return praised.pop(), "contrast"
    return None, "ambiguous"


def wilson(k, n):
    return proportion_confint(k, n, method="wilson") if n else (float("nan"), float("nan"))


def main():
    df = pd.read_csv(ROOT / "runs" / "clean.csv")
    names = name_map()
    flags = fund_flags("grid")
    rec = df.reasoning_text.map(lambda t: recommended_fund(t, names))
    df["recommended_fund"] = [r[0] for r in rec]
    df["basis"] = [r[1] for r in rec]
    df["classifiable"] = df.recommended_fund.notna()
    df["mismatch"] = df.classifiable & (df.recommended_fund != df.chosen_fund)

    # ---- per-run detail (for audit) and mismatch summary per model x condition
    detail = df[["run_id", "model_key", "condition_id", "chosen_fund", "recommended_fund", "basis",
                 "mismatch", "reasoning_text"]]
    detail.to_csv(TABLES / "name_id_detail.csv", index=False)

    rows = []
    for (mk, cond), g in df.groupby(["model_key", "condition_id"], sort=False):
        c = g[g.classifiable]
        k, n = int(c.mismatch.sum()), len(c)
        lo, hi = wilson(k, n)
        rows.append({"model_key": mk, "condition_id": cond, "n_runs": len(g), "n_classifiable": n,
                     "n_no_name": int((g.basis == "no_name").sum()), "n_ambiguous": int((g.basis == "ambiguous").sum()),
                     "n_mismatch": k, "mismatch_rate": k / n if n else None, "mismatch_lo": lo, "mismatch_hi": hi,
                     "mismatch_pairs": ";".join(f"{a}->{b}" for a, b in  # output ID -> recommended name
                                                c.loc[c.mismatch, ["chosen_fund", "recommended_fund"]].values),
                     "mismatched_run_ids": ";".join(c.loc[c.mismatch, "run_id"])})
    mism = pd.DataFrame(rows)
    order = {c: i for i, c in enumerate(pd.read_csv(DATA / "conditions.csv").condition_id)}
    mism = mism.sort_values(["model_key", "condition_id"], key=lambda s: s.map(order) if s.name == "condition_id" else s)
    mism.round(4).to_csv(TABLES / "name_id_mismatch.csv", index=False)

    # ---- sensitivity: ID-based vs name-based reading (name wins when it conflicts with the ID)
    df["fund_name_based"] = df.recommended_fund.where(df.classifiable, df.chosen_fund)
    readings = {"id": df.chosen_fund, "name": df.fund_name_based}
    measures = {"f1": lambda s: s == flags["dominant"], "f2": lambda s: s == flags["dominated"],
                "low_fee": lambda s: s.isin(flags["low_fee"])}
    rows = []
    for (mk, cond), idx in df.groupby(["model_key", "condition_id"], sort=False).groups.items():
        row = {"model_key": mk, "condition_id": cond, "n": len(idx)}
        for m, fn in measures.items():
            for rname, col in readings.items():
                k = int(fn(col.loc[idx]).sum())
                lo, hi = wilson(k, len(idx))
                row.update({f"{m}_{rname}_k": k, f"{m}_{rname}_rate": k / len(idx),
                            f"{m}_{rname}_lo": lo, f"{m}_{rname}_hi": hi})
            row[f"{m}_diff_pp"] = 100 * (row[f"{m}_name_rate"] - row[f"{m}_id_rate"])
        rows.append(row)
    sens = pd.DataFrame(rows)
    sens = sens.sort_values(["model_key", "condition_id"], key=lambda s: s.map(order) if s.name == "condition_id" else s)
    sens.round(4).to_csv(TABLES / "name_id_sensitivity.csv", index=False)

    # ---- order test (F1 vs not-F1 across the 3 fixed orders) under both readings
    rows = []
    for mk, g in df[df.condition_id.str.startswith("ord_")].groupby("model_key", sort=False):
        for rname, col in [("id", "chosen_fund"), ("name", "fund_name_based")]:
            f1 = g[col] == flags["dominant"]
            ct = pd.crosstab(g.condition_id, f1)
            rows.append({"model_key": mk, "reading": rname, "n": len(g),
                         "groups": ";".join(f"{c}={f1[g.condition_id == c].mean():.3f}" for c in sorted(g.condition_id.unique())),
                         "p_chi2_f1": chi2_contingency(ct)[1] if ct.shape[1] > 1 else None})
    pd.DataFrame(rows).to_csv(TABLES / "name_id_order_test.csv", index=False)

    pd.set_option("display.width", 200)
    print("Basis counts:\n", df.groupby(["model_key", "basis"]).size().unstack(fill_value=0), "\n")
    print(mism.drop(columns=["mismatched_run_ids"]).round(3).to_string(index=False), "\n")
    cols = ["model_key", "condition_id"] + [f"{m}_{r}_rate" for m in measures for r in readings]
    print(sens[cols].round(3).to_string(index=False))
    print(f"\nTables -> {TABLES.relative_to(ROOT)}/name_id_{{mismatch,sensitivity,order_test,detail}}.csv")


if __name__ == "__main__":
    main()
