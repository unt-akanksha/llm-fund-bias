"""Counts behind the journal draft's statements about the models' stated reasoning (Study 1 v3/v3.1).

Reads the main-run logs in runs/raw_v3/ the way src/v3/analyze.py does (analyzed runs only: run_index < 30 for
API models, < 50 for the local Qwen models; one record per run_id, a later successful retry replacing a failed
call) and prints:
  1. cost mentions in costlier picks under persuasive documents (D3, D5, D7), per model and family
     (words starting with fee, expense or cost);
  2. mentions of the synthetic label in D5 answers (synthetic / fictional / fabricated), and how many of
     those answers still chose the survey's fund;
  3. history / track-record / ten-year-return mentions in Qwen's no-document QQQ picks (Nasdaq-100);
  4. Qwen 7B's no-document IWM picks (Russell 2000): longer track record cited, and IWM's expense ratio
     wrongly called lower;
  5. the invalid picks (no fund from the table), by kind.
Keyword counts show that something was mentioned, not how it was weighed.

usage: python scripts/paper_reasoning_counts.py
"""
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "runs" / "raw_v3"
LOCAL = {"qwen2.5-7b", "qwen2.5-14b"}
COSTLIER = {"sp500": "SPY", "ndx": "QQQ", "russell2000": "IWM", "dow30": "RYDHX"}
FUNDS = {"sp500": {"SPY", "IVV", "VOO"}, "ndx": {"QQQ", "QQQM"}, "russell2000": {"IWM", "VTWO"},
         "dow30": {"RYDHX", "DIA"}}
PERSUASIVE = {"D3", "D5", "D7"}
COST = re.compile(r"\bfee|expense|\bcost", re.I)
LABEL = re.compile(r"synthetic|fictional|fictitious|fabricat", re.I)
HISTORY = re.compile(r"histor|track record|10[- ]?y|ten[- ]year|longer|established|inception|since|older|"
                     r"long-term performance|longevity", re.I)
TRACK_RECORD = re.compile(r"longer (track|history|inception|period)|track record|longer history|inception date|"
                          r"tracking the market for a longer", re.I)
LOWER_EXPENSE = re.compile(r"lower expense|lower expenses|lower fees?\b|lower cost structure|"
                           r"expense ratio is [^.]*lower|times lower", re.I)


def completed(model):
    """Completed calls of the analyzed runs, one per run_id (as in src/v3/analyze.py)."""
    limit = 50 if model in LOCAL else 30
    rows = {}
    with open(RAW / f"main_{model}.jsonl") as f:
        for line in f:
            r = json.loads(line)
            if r.get("model_key") != model or r["run_index"] >= limit:
                continue
            if r["run_id"] not in rows or not r.get("error"):
                rows[r["run_id"]] = r
    return [r for r in rows.values() if not r.get("error")]


def valid(model):
    return [r for r in completed(model) if r.get("chosen_ticker") in FUNDS[r["family"]]]


def text(r):
    return r["reasoning"] or ""


def invalid_kind(r):
    raw = r.get("raw_response") or ""
    if r.get("chosen_raw"):
        return "mistyped ticker"
    try:
        answer = json.loads(raw)
    except json.JSONDecodeError:
        return "malformed JSON"
    if "ticker" not in answer:
        return "missing ticker"
    return "no fund chosen"


def main():
    models = sorted(p.stem[len("main_"):] for p in RAW.glob("main_*.jsonl"))
    print("1. Cost mentioned in costlier picks under persuasive documents (k/n)")
    for m in models:
        c = defaultdict(lambda: [0, 0])
        for r in valid(m):
            if r["context"] in PERSUASIVE and r["chosen_ticker"] == COSTLIER[r["family"]]:
                c[r["family"]][1] += 1
                c[r["family"]][0] += bool(COST.search(text(r)))
        if c:
            print(f"   {m:18s} " + "  ".join(f"{f} {k}/{n}" for f, (k, n) in sorted(c.items())))

    print("\n2. D5 answers that mention the synthetic label (k/n; of those, chose the survey's fund)")
    for m in models:
        k = n = chose = 0
        for r in valid(m):
            if r["context"] == "D5":
                n += 1
                if LABEL.search(text(r)):
                    k += 1
                    chose += r["chosen_ticker"] == COSTLIER[r["family"]]
        print(f"   {m:18s} {k}/{n}; chose target in {chose}")

    print("\n3. Qwen no-document QQQ picks citing history / track record / ten-year return (k/n)")
    for m in sorted(LOCAL):
        picks = [r for r in valid(m) if r["family"] == "ndx" and r["context"] == "baseline"
                 and r["chosen_ticker"] == "QQQ"]
        print(f"   {m:18s} {sum(bool(HISTORY.search(text(r))) for r in picks)}/{len(picks)}")

    print("\n4. Qwen 7B no-document IWM picks (Russell 2000)")
    picks = [r for r in valid("qwen2.5-7b") if r["family"] == "russell2000" and r["context"] == "baseline"
             and r["chosen_ticker"] == "IWM"]
    print(f"   cite IWM's longer track record: {sum(bool(TRACK_RECORD.search(text(r))) for r in picks)}/{len(picks)}")
    print(f"   call IWM's expense ratio or fees lower: {sum(bool(LOWER_EXPENSE.search(text(r))) for r in picks)}/{len(picks)}")

    print("\n5. Invalid picks (no fund from the table)")
    kinds = Counter()
    for m in models:
        for r in completed(m):
            if r.get("chosen_ticker") not in FUNDS[r["family"]]:
                kind = invalid_kind(r)
                kinds[kind] += 1
                answer = text(r) or r.get("raw_response") or ""
                print(f"   {m:18s} {r['family']:12s} {r['context']:8s} {kind:16s} {answer[-110:]!r}")
    print(f"   total {sum(kinds.values())}: " + ", ".join(f"{v} {k}" for k, v in kinds.most_common()))


if __name__ == "__main__":
    main()
