"""Study 1 v2 MAIN RUN (frozen design, tag v2.0-frozen-design). Resumable; two passes with a quality gate.

  python src/v2/run_main.py --dry-run
  python src/v2/run_main.py                 # Pass 1 -> gate -> Pass 2 (stops if the gate fails)
  python src/v2/run_main.py --gate-only     # re-run the Pass 1 gate on existing logs

Pass 1 (50 runs per cell): baseline__real, baseline__masked, D1__real, D3__real, D5__real, W1..W4__real.
Gate after Pass 1 (per model x Pass 1 cell; any failure -> STOP, Pass 2 not started):
  - planned = completed (successful calls);
  - name-vs-ID mismatch <= 2% of classifiable responses (fund named in the reasoning vs ticker output);
  - invalid/unparsed tickers (not in the table shown) <= 2%;
  - output-cap hits (tokens_out >= max_tokens, i.e. finish_reason 'length') <= 2%;
  - choice shares over valid picks sum to 1;
  - 20 random raw responses (fixed seed) written to runs/v2_pass1_sample.txt for the author.
Pass 2: every cell (all 26 main cells) extended to 100 runs.

Logs: runs/raw_v2/main_<model>.jsonl (append-only). Progress: runs/v2_main_progress.log (status line every
15 minutes). No analysis is run here.
"""

import argparse
import json
import random
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from common import read_jsonl, stable_seed  # noqa: E402
from name_id_check import recommended_fund  # noqa: E402  (study 1 detector, unchanged)
from providers import call_model, check_ollama  # noqa: E402

from v2 import render  # noqa: E402

CONFIG = ROOT / "config" / "models_v2.yaml"
LOGDIR = ROOT / "runs" / "raw_v2"
PROGRESS = ROOT / "runs" / "v2_main_progress.log"
SAMPLE = ROOT / "runs" / "v2_pass1_sample.txt"
GATE = ROOT / "runs" / "v2_gate_pass1.txt"
PHASE = "main"
TARGETS = {"best": "IVV", "worst": "SPY"}          # design §3/§4.1 with the verified data (frozen)
PASS1 = ["baseline__real", "baseline__masked", "D1__real", "D3__real", "D5__real",
         "W1__real", "W2__real", "W3__real", "W4__real"]
PASS1_RUNS, FULL_RUNS = 50, 100
GATE_MAX = 0.02
STATUS_EVERY_S = 15 * 60
MAX_CONSEC_ERRORS = 3


def log_progress(msg):
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {msg}"
    with open(PROGRESS, "a") as f:
        f.write(line + "\n")
    print(line, flush=True)


def messages_for(c, i, funds, tickers):
    order = render.row_order(tickers, PHASE, i)
    docs = []
    if c["documents"]:
        for d, role in zip(c["documents"].split("|"), c["target_roles"].split("|")):
            tpl = (render.SOURCES_V2 / f"{d}.txt").read_text()
            docs.append(render.fill_document(tpl, TARGETS[role], funds, c["naming"]))
    return render.build_messages(funds, order, c["naming"], docs, c["memory"] or None), order


def parse(text, naming, masks_rev):
    """-> (chosen real ticker or None, raw ticker, reasoning)."""
    try:
        obj = json.loads(text)
        raw = str(obj.get("ticker", "")).strip().upper()
        reasoning = obj.get("reasoning")
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None, None, None
    raw = re.sub(r"^(NYSE|NASDAQ|NYSEARCA)\s*:\s*", "", raw)
    real = masks_rev.get(raw) if naming == "masked" else raw
    return real, raw, reasoning


def name_map(funds, naming):
    """{regex-escaped name or ticker: real ticker} for the study 1 detector (real names or masked codes)."""
    masks = render.mask_map([f["ticker"] for f in funds])
    out = {}
    for f in funds:
        if naming == "masked":
            code, mname = masks[f["ticker"]]
            out[re.escape(mname)] = f["ticker"]
            out[code] = f["ticker"]
        else:
            out[re.escape(f["fund_name"])] = f["ticker"]
            out[f["ticker"]] = f["ticker"]
    return out


def jobs_for(cells, n_runs, conds):
    return [(conds[c], i) for i in range(n_runs) for c in cells]   # interleave cells run by run


def run_pass(name, cells, n_runs, cfg, models, funds, conds):
    tickers = [f["ticker"] for f in funds]
    masks = render.mask_map(tickers)
    masks_rev = {code: t for t, (code, _) in masks.items()}
    valid = set(tickers)
    max_tokens = cfg["defaults"]["params"]["max_tokens"]
    for mk in models:
        mcfg = cfg["models"][mk]
        digest = check_ollama(cfg, mcfg["model_id"])
        path = LOGDIR / f"main_{mk}.jsonl"
        done = {r["run_id"] for r in read_jsonl(path) if not r.get("error")}
        todo = [(c, i) for c, i in jobs_for(cells, n_runs, conds) if f"{PHASE}|{c['condition_id']}|{i:04d}|{mk}" not in done]
        log_progress(f"{name} {mk}: {len(todo)} calls to run ({len(done)} already done for this model)")
        errors = n = bad = 0
        last_status = time.time()
        for c, i in todo:
            rid = f"{PHASE}|{c['condition_id']}|{i:04d}|{mk}"
            msgs, order = messages_for(c, i, funds, tickers)
            seed = stable_seed("v2", c["condition_id"], i)
            res = call_model(cfg, mcfg, msgs, seed)
            chosen, raw, reasoning = (None, None, None) if res["error"] else parse(res["raw_response"], c["naming"], masks_rev)
            rec = {"run_id": rid, "phase": PHASE, "pass": name, "condition_id": c["condition_id"],
                   "base_condition": c["base_condition"], "naming": c["naming"], "run_index": i, "model_key": mk,
                   "provider": mcfg["provider"], "model_id": mcfg["model_id"], "model_digest": digest, "seed": seed,
                   "temperature": cfg["defaults"]["params"]["temperature"], "max_tokens": max_tokens,
                   "num_ctx": cfg["defaults"]["params"]["num_ctx"], "row_order": order,
                   "documents": c["documents"], "target_roles": c["target_roles"], "memory": c["memory"],
                   "chosen_ticker": chosen, "chosen_raw": raw, "reasoning": reasoning,
                   "hit_output_cap": bool(res.get("tokens_out") and res["tokens_out"] >= max_tokens),
                   "timestamp": datetime.now(timezone.utc).isoformat(), **res}
            with open(path, "a") as f:
                f.write(json.dumps(rec) + "\n")
            n += 1
            errors = errors + 1 if res["error"] else 0
            bad += int(bool(res["error"]) or chosen not in valid)
            if errors >= MAX_CONSEC_ERRORS:
                log_progress(f"AUTO-STOP {mk}: {errors} consecutive errors (Ollama down?). Last: {res['error']}")
                sys.exit(2)
            if n >= 40 and bad / n > 0.05:
                log_progress(f"AUTO-STOP {mk}: {bad}/{n} calls failed or gave an invalid ticker (> 5%)")
                sys.exit(3)
            if time.time() - last_status >= STATUS_EVERY_S:
                log_progress(f"STATUS {name} {mk}: {n}/{len(todo)} this pass, errors-or-invalid {bad}, "
                             f"last {c['condition_id']} run {i}, {res['latency_ms'] / 1000:.1f}s/call")
                last_status = time.time()
        log_progress(f"{name} {mk}: finished {n} calls ({bad} failed/invalid)")


def gate(cfg, models, funds, conds):
    tickers = [f["ticker"] for f in funds]
    valid = set(tickers)
    lines, fails, sample_pool = [], [], []
    for mk in models:
        recs = {}
        for r in read_jsonl(LOGDIR / f"main_{mk}.jsonl"):
            if not r.get("error") and r["condition_id"] in PASS1 and r["run_index"] < PASS1_RUNS:
                recs[r["run_id"]] = r
        for cid in PASS1:
            rs = [r for r in recs.values() if r["condition_id"] == cid]
            n = len(rs)
            invalid = sum(1 for r in rs if r["chosen_ticker"] not in valid)
            capped = sum(1 for r in rs if r["hit_output_cap"])
            naming = conds[cid]["naming"]
            names = name_map(funds, naming)
            cls = mism = 0
            for r in rs:
                if r["chosen_ticker"] not in valid:
                    continue
                rec_t, _ = recommended_fund(r.get("reasoning") or "", names)
                if rec_t:
                    cls += 1
                    mism += int(rec_t != r["chosen_ticker"])
            picks = Counter(r["chosen_ticker"] for r in rs if r["chosen_ticker"] in valid)
            share_sum = sum(v / sum(picks.values()) for v in picks.values()) if picks else 0.0
            checks = {"planned=completed": n == PASS1_RUNS,
                      "name-vs-ID<=2%": (mism / cls if cls else 0) <= GATE_MAX,
                      "invalid<=2%": invalid / max(n, 1) <= GATE_MAX,
                      "output-cap<=2%": capped / max(n, 1) <= GATE_MAX,
                      "shares sum to 1": abs(share_sum - 1) < 1e-9}
            lines.append(f"{mk:<12} {cid:<18} n={n:<3} name/ID mismatch {mism}/{cls} | invalid {invalid} | "
                         f"cap hits {capped} | " + " ".join(f"{k}:{'PASS' if v else 'FAIL'}" for k, v in checks.items()))
            fails += [f"{mk} {cid}: {k}" for k, v in checks.items() if not v]
            sample_pool += rs
    rng = random.Random(20261020)
    sample = rng.sample(sorted(sample_pool, key=lambda r: r["run_id"]), min(20, len(sample_pool)))
    with open(SAMPLE, "w") as f:
        for r in sample:
            f.write(f"--- {r['run_id']} (chosen {r['chosen_ticker']})\n{r['raw_response']}\n\n")
    verdict = "PASS" if not fails else "FAIL: " + "; ".join(fails)
    GATE.write_text("\n".join(lines) + f"\n\nGATE PASS 1: {verdict}\n20 random raw responses: {SAMPLE.name}\n")
    log_progress(f"GATE PASS 1: {verdict} (details {GATE.name}; sample {SAMPLE.name})")
    return not fails


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default="llama3.1-8b,qwen2.5-7b")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--gate-only", action="store_true")
    a = ap.parse_args()
    models = a.models.split(",")
    cfg = yaml.safe_load(open(CONFIG))
    funds = render.load_funds(render.FILLED_CSV, placeholder=False)
    conds = {c["condition_id"]: c for c in render.load_conditions() if c["block"] in ("core", "order")}
    main_cells = list(conds)
    n1 = len(PASS1) * PASS1_RUNS
    n2 = len(main_cells) * FULL_RUNS - n1
    if a.dry_run:
        print(f"Pass 1: {len(PASS1)} cells x {PASS1_RUNS} = {n1} calls/model; Pass 2: {n2} calls/model; "
              f"total {n1 + n2}/model, {(n1 + n2) * len(models)} overall")
        return
    LOGDIR.mkdir(parents=True, exist_ok=True)
    if a.gate_only:
        sys.exit(0 if gate(cfg, models, funds, conds) else 1)
    log_progress(f"START main run (models {models}); Pass 1 {n1}/model, Pass 2 {n2}/model")
    run_pass("PASS1", PASS1, PASS1_RUNS, cfg, models, funds, conds)
    if not gate(cfg, models, funds, conds):
        log_progress("STOPPED after Pass 1: quality gate failed. Pass 2 not started. Waiting for the author.")
        sys.exit(1)
    run_pass("PASS2", main_cells, FULL_RUNS, cfg, models, funds, conds)
    log_progress("MAIN RUN COMPLETE. No analysis run.")


if __name__ == "__main__":
    main()
