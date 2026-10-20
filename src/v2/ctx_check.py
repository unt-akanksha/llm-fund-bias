"""Study 1 v2 context-overflow check (pre-freeze): one real call per condition per model.

  python src/v2/ctx_check.py            # 28 conditions x 2 models = 56 calls; logs runs/raw_v2/ctxcheck_<model>.jsonl
  python src/v2/ctx_check.py --report   # max prompt_eval_count per model; flag > 80% of num_ctx

Uses the real documents (data/sources_v2) with targets best = IVV, worst = SPY (design §3, §4.1) and run 0
of each condition's row order. Not part of any analysis.
"""

import argparse
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from common import read_jsonl, stable_seed  # noqa: E402
from providers import call_model, check_ollama  # noqa: E402

from v2 import render  # noqa: E402

CONFIG = ROOT / "config" / "models_v2.yaml"
LOGDIR = ROOT / "runs" / "raw_v2"
TARGETS = {"best": "IVV", "worst": "SPY"}
LIMIT_SHARE = 0.80


def condition_messages(c, funds):
    phase = "pilot" if c["block"] == "pilot" else "main"
    order = render.row_order([f["ticker"] for f in funds], phase, 0)
    docs = []
    if c["documents"]:
        for d, role in zip(c["documents"].split("|"), c["target_roles"].split("|")):
            tpl = (render.SOURCES_V2 / f"{d}.txt").read_text()
            docs.append(render.fill_document(tpl, TARGETS[role], funds, c["naming"]))
    return render.build_messages(funds, order, c["naming"], docs, c["memory"] or None)


def run(models):
    cfg = yaml.safe_load(open(CONFIG))
    funds = render.load_funds(render.FILLED_CSV, placeholder=False)
    LOGDIR.mkdir(parents=True, exist_ok=True)
    for mk in models:
        mcfg = cfg["models"][mk]
        check_ollama(cfg, mcfg["model_id"])
        path = LOGDIR / f"ctxcheck_{mk}.jsonl"
        done = {r["condition_id"] for r in read_jsonl(path) if not r.get("error")}
        for c in render.load_conditions():
            if c["condition_id"] in done:
                continue
            msgs = condition_messages(c, funds)
            res = call_model(cfg, mcfg, msgs, stable_seed("v2ctx", c["condition_id"]))
            rec = {"condition_id": c["condition_id"], "model_key": mk, "num_ctx": cfg["defaults"]["params"]["num_ctx"],
                   "approx_tokens": render.approx_tokens(msgs), **res}
            with open(path, "a") as f:
                f.write(json.dumps(rec) + "\n")
            print(f"{mk} {c['condition_id']:<24} prompt_eval={res['tokens_in']} eval={res['tokens_out']} "
                  f"{res['latency_ms']} ms{'  ERR ' + res['error'] if res['error'] else ''}", flush=True)


def report(models):
    cfg = yaml.safe_load(open(CONFIG))
    num_ctx = cfg["defaults"]["params"]["num_ctx"]
    for mk in models:
        recs = [r for r in read_jsonl(LOGDIR / f"ctxcheck_{mk}.jsonl") if not r.get("error")]
        top = max(recs, key=lambda r: r["tokens_in"])
        over = [r["condition_id"] for r in recs if r["tokens_in"] > LIMIT_SHARE * num_ctx]
        full = [r["condition_id"] for r in recs if r["tokens_in"] + r["tokens_out"] >= num_ctx]
        print(f"{mk}: {len(recs)} conditions | max prompt_eval_count {top['tokens_in']} ({top['condition_id']}) | "
              f"> {int(LIMIT_SHARE * num_ctx)}: {over or 'none'} | prompt+eval >= num_ctx: {full or 'none'}")
        for r in recs:
            print(f"   {r['condition_id']:<24} {r['tokens_in']:>5} in  {r['tokens_out']:>4} out  ({r['latency_ms'] / 1000:.1f} s)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default="llama3.1-8b,qwen2.5-7b")
    ap.add_argument("--report", action="store_true")
    a = ap.parse_args()
    (report if a.report else run)(a.models.split(","))
