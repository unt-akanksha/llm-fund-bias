"""Study 1 v2 PILOT (design_v2.md §6.1, §7): baseline real + name-masked, and the masked-identification probe.

  python src/v2/run_pilot.py --dry-run
  python src/v2/run_pilot.py                 # 2 models x (60 baseline + 13 probe) = 146 calls
  python src/v2/run_pilot.py --report        # tokens, seconds, failures, identification, cluster shares

Logs (append-only, resumable): runs/raw_v2/pilot_<model>.jsonl. Pilot data is never used in the
confirmatory analysis. Uses the shared src/providers.call_model (unchanged) with config/models_v2.yaml.
"""

import argparse
import csv
import json
import statistics
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from common import read_jsonl, stable_seed  # noqa: E402
from providers import call_model, check_ollama  # noqa: E402

from v2 import render  # noqa: E402

CONFIG = ROOT / "config" / "models_v2.yaml"
LOGDIR = ROOT / "runs" / "raw_v2"
PHASE = "pilot"
CLUSTERS = ["sp500", "nasdaq100", "total_us", "us_agg_bond", "international"]


def probe_messages(funds, code):
    order = render.row_order([f["ticker"] for f in funds], PHASE, 0)
    table = render.fund_table(funds, order, "masked")
    return [{"role": "user", "content":
             "Here is a table of funds with their names and tickers hidden:\n\n" + table +
             f"\n\nWhich real fund do you think {code} is? Respond with only a JSON object with exactly two "
             'keys, in this order: "reasoning" (1-2 sentences), then "ticker" (the real ticker you think '
             f'{code} is). Format: {{"reasoning": "...", "ticker": "..."}}'}]


def plan(cfg, funds):
    """[(run_id, kind, condition_id, naming, i, messages, extra)] for every pilot call."""
    jobs = []
    conds = [c for c in render.load_conditions() if c["block"] == "pilot"]
    tickers = [f["ticker"] for f in funds]
    for c in conds:
        for i in range(int(c["runs"])):
            order = render.row_order(tickers, PHASE, i)
            msgs = render.build_messages(funds, order, c["naming"])
            jobs.append((f"{PHASE}|{c['condition_id']}|{i:04d}", "baseline", c["condition_id"], c["naming"], i, msgs,
                         {"row_order": order}))
    masks = render.mask_map(tickers)
    for t, (code, _) in sorted(masks.items(), key=lambda kv: kv[1][0]):
        jobs.append((f"{PHASE}|probe|{code}", "probe", "probe", "masked", 0, probe_messages(funds, code),
                     {"probe_code": code, "probe_true_ticker": t}))
    return jobs


def parse_ticker(text):
    try:
        obj = json.loads(text)
        return str(obj.get("ticker", "")).strip().upper() or None, obj.get("reasoning")
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None, None


def run(models, dry):
    cfg = yaml.safe_load(open(CONFIG))
    funds = render.load_funds(render.FILLED_CSV, placeholder=False)
    jobs = plan(cfg, funds)
    print(f"Pilot plan: {len(jobs)} calls per model x {len(models)} models = {len(jobs) * len(models)}")
    if dry:
        return
    LOGDIR.mkdir(parents=True, exist_ok=True)
    for mk in models:
        mcfg = cfg["models"][mk]
        digest = check_ollama(cfg, mcfg["model_id"])
        path = LOGDIR / f"pilot_{mk}.jsonl"
        done = {r["run_id"] for r in read_jsonl(path) if not r.get("error")}
        errors = 0
        for run_id, kind, cond, naming, i, msgs, extra in jobs:
            rid = f"{run_id}|{mk}"
            if rid in done:
                continue
            seed = stable_seed("v2pilot", cond, naming, i, extra.get("probe_code", ""))
            res = call_model(cfg, mcfg, msgs, seed)
            ticker, reasoning = (None, None) if res["error"] else parse_ticker(res["raw_response"])
            now = datetime.now(timezone.utc)
            rec = {"run_id": rid, "phase": PHASE, "kind": kind, "condition_id": cond, "naming": naming,
                   "run_index": i, "model_key": mk, "provider": mcfg["provider"], "model_id": mcfg["model_id"],
                   "model_digest": digest, "seed": seed, "num_ctx": cfg["defaults"]["params"]["num_ctx"],
                   "temperature": cfg["defaults"]["params"]["temperature"], "timestamp": now.isoformat(),
                   "chosen_ticker_raw": ticker, "reasoning": reasoning, **extra, **res}
            with open(path, "a") as f:
                f.write(json.dumps(rec) + "\n")
            errors = errors + 1 if res["error"] else 0
            print(f"{rid}  {res['latency_ms']} ms  in={res['tokens_in']} out={res['tokens_out']}  ticker={ticker}"
                  f"{'  ERR ' + res['error'] if res['error'] else ''}", flush=True)
            if errors >= 3:
                sys.exit(f"AUTO-STOP {mk}: 3 consecutive errors")


def report(models):
    funds = render.load_funds(render.FILLED_CSV, placeholder=False)
    by = {f["ticker"]: f for f in funds}
    masks = render.mask_map(list(by))
    code_to_ticker = {code: t for t, (code, _) in masks.items()}
    out = {}
    for mk in models:
        recs = [r for r in read_jsonl(LOGDIR / f"pilot_{mk}.jsonl") if not r.get("error")]
        allr = read_jsonl(LOGDIR / f"pilot_{mk}.jsonl")
        base = [r for r in recs if r["kind"] == "baseline"]
        probe = [r for r in recs if r["kind"] == "probe"]
        lat = [r["latency_ms"] / 1000 for r in recs]
        row = {"calls_ok": len(recs), "errors": sum(1 for r in allr if r.get("error")),
               "tokens_in_median_baseline_real": statistics.median(r["tokens_in"] for r in base if r["naming"] == "real"),
               "tokens_in_median_baseline_masked": statistics.median(r["tokens_in"] for r in base if r["naming"] == "masked"),
               "tokens_out_median": statistics.median(r["tokens_out"] for r in base),
               "tokens_out_max": max(r["tokens_out"] for r in base),
               "sec_per_call_median": round(statistics.median(lat), 2), "sec_per_call_p90": round(sorted(lat)[int(.9 * len(lat)) - 1], 2)}
        for naming in ("real", "masked"):
            picks = []
            unparsed = 0
            for r in base:
                if r["naming"] != naming:
                    continue
                t = r["chosen_ticker_raw"]
                t = code_to_ticker.get(t, t) if naming == "masked" else t
                if t in by:
                    picks.append(by[t]["cluster"])
                else:
                    unparsed += 1
            n = sum(1 for r in base if r["naming"] == naming)
            row[f"{naming}_n"] = n
            row[f"{naming}_invalid_or_unparsed"] = unparsed
            c = Counter(picks)
            for cl in CLUSTERS:
                row[f"{naming}_{cl}"] = round(c[cl] / n, 3) if n else None
            row[f"{naming}_fund_counts"] = dict(Counter((code_to_ticker.get(r["chosen_ticker_raw"], r["chosen_ticker_raw"])
                                                        if naming == "masked" else r["chosen_ticker_raw"])
                                                       for r in base if r["naming"] == naming))
        ident = sum(1 for r in probe if r["chosen_ticker_raw"] == r["probe_true_ticker"])
        same_index = sum(1 for r in probe if r["chosen_ticker_raw"] in by and
                         by[r["chosen_ticker_raw"]]["index_tracked"] == by[r["probe_true_ticker"]]["index_tracked"])
        row.update({"probe_n": len(probe), "probe_identified": ident, "probe_same_index": same_index,
                    "probe_answers": {r["probe_code"]: f"{r['probe_true_ticker']}->{r['chosen_ticker_raw']}" for r in probe}})
        out[mk] = row
    print(json.dumps(out, indent=1))
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default="llama3.1-8b,qwen2.5-7b")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    ms = a.models.split(",")
    report(ms) if a.report else run(ms, a.dry_run)
