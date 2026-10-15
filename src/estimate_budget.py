"""Budget estimate for running the own-maker study on paid frontier models.

  python src/estimate_budget.py                      # default: 500 Stage 1 + 100 Stage 2 calls per model
  python src/estimate_budget.py --stage1-calls 1000 --stage2-calls 100 --models claude-opus-5.5,gpt-6.1-sol
  python src/estimate_budget.py --dry-run            # only print the measured token inputs

Tokens per call are measured, not assumed: input tokens from the real prompts (chars/4, cross-checked
against logged prompt tokens), output tokens from the Stage 1 logs. Scenarios:
  low    = shortest measured outputs (non-reasoning small models)
  likely = largest non-reasoning median (qwen3.8-27b on Groq)
  high   = reasoning-model upper bound: the output cap used for gpt-oss-120b (hidden reasoning billed as output)
Prices: studies/own_maker/config/prices.yaml (official pages, with access date). Writes studies/own_maker/results/tables/budget_estimate.csv.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
STUDY = ROOT / "studies" / "own_maker"
sys.path.insert(0, str(STUDY / "src"))


def measured_tokens():
    """Per-scenario (tokens_in, tokens_out) for Stage 1 and Stage 2, from logs and rendered prompts."""
    logs = {}
    for p in (STUDY / "runs" / "raw").glob("stage1_*.jsonl"):
        if "_maker_" in p.name:
            continue
        mk = p.stem.split("_", 2)[2]
        recs = [json.loads(line) for line in open(p) if line.strip()]
        logs.setdefault(mk, []).extend(r for r in recs if not r.get("error"))
    med = {mk: (statistics.median(r["tokens_in"] for r in rs), statistics.median(r["tokens_out"] for r in rs))
           for mk, rs in logs.items() if rs}
    non_reasoning = {k: v for k, v in med.items() if "gpt-oss" not in k}
    s1_in = max(v[0] for v in med.values())                       # largest logged prompt (incl. provider overhead)
    s1_out_low = min(v[1] for v in non_reasoning.values())
    s1_out_likely = max(v[1] for v in non_reasoning.values())
    gpt_cap = yaml.safe_load(open(STUDY / "config" / "models.yaml"))["models"]["groq-gpt-oss-120b"]["params"]["max_tokens"]

    import stage2_design as S2
    cfg, pr = S2.load()
    chars = statistics.mean(sum(len(m["content"]) for m in S2.messages(cfg, pr, i, c)[0])
                            for i in range(10) for c in ("real_names", "fictional_names"))
    s2_in = chars / 4 + 20                                         # ~4 chars/token + chat-format overhead
    s2_out_low, s2_out_likely = 80, 150                            # 2-3 sentence reasoning + ticker (study 1 logs: 60-93)
    return {"stage1": {"low": (s1_in, s1_out_low), "likely": (s1_in, s1_out_likely), "high": (s1_in, gpt_cap)},
            "stage2": {"low": (s2_in, s2_out_low), "likely": (s2_in, s2_out_likely), "high": (s2_in, gpt_cap)},
            "_medians": med}


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--stage1-calls", type=int, default=500, help="per model (10 prompts x 50 runs)")
    ap.add_argument("--stage2-calls", type=int, default=100, help="per model (2 conditions x 50 runs)")
    ap.add_argument("--models", help="comma-separated keys from config/prices.yaml (default: all)")
    ap.add_argument("--dry-run", action="store_true", help="print measured token inputs only")
    a = ap.parse_args()

    tok = measured_tokens()
    print("Logged Stage 1 medians (tokens_in, tokens_out):", {k: v for k, v in tok["_medians"].items()})
    for st in ("stage1", "stage2"):
        print(f"{st}: " + ", ".join(f"{s} in={i:.0f} out={o:.0f}" for s, (i, o) in tok[st].items()))
    if a.dry_run:
        return

    prices = yaml.safe_load(open(STUDY / "config" / "prices.yaml"))
    models = a.models.split(",") if a.models else list(prices["models"])
    calls = {"stage1": a.stage1_calls, "stage2": a.stage2_calls}
    rows = []
    for m in models:
        p = prices["models"][m]
        for st, n in calls.items():
            row = {"model": m, "stage": st, "calls": n}
            for s, (ti, to) in tok[st].items():
                row[f"tokens_in_{s}"] = round(n * ti)
                row[f"tokens_out_{s}"] = round(n * to)
                row[f"usd_{s}"] = (n * ti * p["input"] + n * to * p["output"]) / 1e6
            rows.append(row)
    df = pd.DataFrame(rows)
    out = STUDY / "results" / "tables" / "budget_estimate.csv"
    df.round(2).to_csv(out, index=False)
    pd.set_option("display.width", 200)
    print(df[["model", "stage", "calls", "tokens_in_likely", "tokens_out_likely", "usd_low", "usd_likely", "usd_high"]]
          .round(2).to_string(index=False))
    tot = df.groupby("model")[["usd_low", "usd_likely", "usd_high"]].sum().round(2)
    print("\nTotal per model (Stage 1 + Stage 2), USD:\n" + tot.to_string())
    print(f"\nPrices accessed {prices['accessed']}: " + "; ".join(prices["sources"].values()))
    print("Unverified: " + " | ".join(prices["unverified"]))
    print(f"-> {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
