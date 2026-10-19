"""Study 1 v2 reasoning coder (design_v2.md §4.3): dictionary rules, hand-coding sample, Cohen's kappa.

  python src/v2/reasoning_codes.py sample --responses runs/v2_clean.csv --out hand_coding_sample.csv
  python src/v2/reasoning_codes.py kappa  --coded hand_coding_sample.csv

Codes (binary). The first four together form the key outcome CITES_COST:
  cites_expense_ratio, cites_tracking_difference, cites_spread_liquidity, cites_cost_generic,
  cites_brand_size_aum, cites_authority_source, cites_past_returns, cites_structure

Rule-based coding is used in results only for codes with Cohen's kappa >= 0.7 against the author's
hand coding of 100 responses, stratified by condition.
"""

import argparse
import csv
import random
import re
from collections import defaultdict

KAPPA_MIN = 0.7
SAMPLE_N = 100
SAMPLE_SEED = 20261019

RULES = {
    "cites_expense_ratio": [r"expense ratio", r"\bER\b", r"management fee", r"\bfees?\b", r"\b0?\.\d+\s?%\s*(?:fee|expense)"],
    "cites_tracking_difference": [r"tracking (?:difference|error)", r"tracks? (?:the )?index (?:closely|tightly|well)",
                                  r"(?:lags?|trails?) (?:its|the) (?:index|benchmark)"],
    "cites_spread_liquidity": [r"bid[- /]ask", r"\bspread", r"liquid(?:ity)?", r"trading (?:volume|costs?)"],
    "cites_cost_generic": [r"\blow[- ]cost", r"\bcheap(?:er|est)?\b", r"\bcost[- ]effective", r"\bcosts?\b",
                           r"\binexpensive\b", r"\bexpenses?\b"],
    "cites_brand_size_aum": [r"\bAUM\b", r"assets under management", r"\blargest\b", r"\bpopular", r"\bwell[- ]known",
                             r"\breputation", r"\bbrand", r"\btrusted\b", r"\bsize\b", r"\bnet assets\b"],
    "cites_authority_source": [r"\banalysts?\b", r"\bexperts?\b", r"\bstud(?:y|ies)\b", r"\bresearch(?:ers)?\b",
                               r"\baccording to\b", r"\brecommend(?:ed|s|ation) by\b", r"\bstrategists?\b", r"\breport\b"],
    "cites_past_returns": [r"\breturns?\b", r"\bperform(?:ance|ed)\b", r"\boutperform", r"\btrack record\b",
                           r"\b\d{1,2}-?(?:yr|year)\b"],
    "cites_structure": [r"unit investment trust", r"\bUIT\b", r"open-end", r"\bstructure\b", r"\bsecurities lending\b"],
}
CODES = list(RULES)
COST_CODES = CODES[:4]
_COMPILED = {c: [re.compile(p, re.I) for p in pats] for c, pats in RULES.items()}


def code_reasoning(text):
    """Dictionary codes for one reasoning text -> {code: 0/1, 'cites_cost': 0/1}."""
    text = text or ""
    out = {c: int(any(rx.search(text) for rx in _COMPILED[c])) for c in CODES}
    out["cites_cost"] = int(any(out[c] for c in COST_CODES))
    return out


def stratified_sample(rows, n=SAMPLE_N, seed=SAMPLE_SEED, key="condition_id"):
    """Sample n rows spread as evenly as possible across conditions (seeded, reproducible)."""
    rng = random.Random(seed)
    groups = defaultdict(list)
    for r in rows:
        groups[r[key]].append(r)
    for g in groups.values():
        rng.shuffle(g)
    names = sorted(groups)
    picked, i = [], 0
    while len(picked) < min(n, len(rows)):
        g = groups[names[i % len(names)]]
        if g:
            picked.append(g.pop())
        i += 1
    return picked


def cohen_kappa(a, b):
    """Cohen's kappa for two equal-length binary (0/1) sequences. Returns None if undefined."""
    if len(a) != len(b) or not a:
        raise ValueError("need two equal-length, non-empty sequences")
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    pa1, pb1 = sum(a) / n, sum(b) / n
    pe = pa1 * pb1 + (1 - pa1) * (1 - pb1)
    if pe == 1:
        return None   # both coders constant and identical: kappa undefined
    return (po - pe) / (1 - pe)


def kappa_report(coded_rows):
    """coded_rows: dicts with auto_<code> and human_<code> columns (0/1). Returns {code: (kappa, n, usable)}."""
    out = {}
    for c in CODES + ["cites_cost"]:
        pairs = [(int(r[f"auto_{c}"]), int(r[f"human_{c}"])) for r in coded_rows
                 if str(r.get(f"human_{c}", "")).strip() in ("0", "1")]
        if not pairs:
            out[c] = (None, 0, False)
            continue
        k = cohen_kappa([p[0] for p in pairs], [p[1] for p in pairs])
        out[c] = (k, len(pairs), k is not None and k >= KAPPA_MIN)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("sample")
    s.add_argument("--responses", required=True, help="CSV with run_id, condition_id, reasoning_text")
    s.add_argument("--out", required=True)
    k = sub.add_parser("kappa")
    k.add_argument("--coded", required=True)
    a = ap.parse_args()
    if a.cmd == "sample":
        rows = list(csv.DictReader(open(a.responses)))
        picked = stratified_sample(rows)
        fields = ["run_id", "condition_id", "reasoning_text"] + [f"auto_{c}" for c in CODES + ["cites_cost"]] \
            + [f"human_{c}" for c in CODES + ["cites_cost"]]
        with open(a.out, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            for r in picked:
                codes = code_reasoning(r["reasoning_text"])
                w.writerow({"run_id": r["run_id"], "condition_id": r["condition_id"],
                            "reasoning_text": r["reasoning_text"],
                            **{f"auto_{c}": v for c, v in codes.items()},
                            **{f"human_{c}": "" for c in codes}})
        print(f"Wrote {len(picked)} rows to {a.out}; fill the human_* columns with 0/1, then run 'kappa'.")
    else:
        for c, (kap, n, ok) in kappa_report(list(csv.DictReader(open(a.coded)))).items():
            print(f"{c:<28} n={n:<4} kappa={'undefined' if kap is None else f'{kap:.2f}'}  "
                  f"{'usable' if ok else 'NOT usable (< 0.7)'}")


if __name__ == "__main__":
    main()
