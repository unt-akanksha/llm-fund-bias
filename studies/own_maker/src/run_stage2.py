"""Own-maker study, Stage 2: pick one stock from 10 companies with HYPOTHETICAL (made-up) financials.

  python studies/own_maker/src/run_stage2.py --dry-run
  python studies/own_maker/src/run_stage2.py --yes          # all models x conditions x runs (config)

Design: stage2/config.yaml and stage2/prompt.yaml (frozen at tag own-maker-stage2-v1). Logs:
runs/raw/stage2_<phase>_<model>.jsonl (append-only, resumable). Each record carries the condition,
the rank of every company, the row order, the chosen ticker and the matching company slot.
Auto-stop: >5% calls with an error or no valid ticker (from call 40), or 3 consecutive errors.
Not financial advice: the figures describe no real company.
"""

import argparse
import hashlib
import json
import re
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

STUDY = Path(__file__).resolve().parent.parent
REPO = STUDY.parent.parent
sys.path.insert(0, str(REPO / "src"))
from common import read_jsonl, stable_seed  # noqa: E402
from providers import call_model, check_ollama  # noqa: E402

import stage2_design as S2  # noqa: E402

RAW = STUDY / "runs" / "raw"
MODELS = STUDY / "config" / "models.yaml"
CONDITIONS = ("real_names", "fictional_names")
MAX_CONSECUTIVE_ERRORS, MAX_FAIL_RATE, MIN_CALLS_FOR_RATE = 3, 0.05, 40
DEFAULT_SEC_PER_CALL = 10.0


def design_sha():
    return hashlib.sha256(S2.CFG.read_bytes() + S2.PROMPT.read_bytes()).hexdigest()


def parse_pick(text, names):
    """Return (slot or None, raw ticker). JSON 'ticker' first; else the only ticker/name mentioned."""
    tickers = [n["ticker"].upper() for n in names]
    raw = None
    try:
        obj = json.loads(text)
        raw = str(obj.get("ticker", "")).strip()
    except (json.JSONDecodeError, TypeError, AttributeError):
        m = re.search(r'"ticker"\s*:\s*"([^"]*)"', text or "")
        raw = m.group(1) if m else None
    if raw:
        t = re.sub(r"^(NASDAQ|NYSE)\s*:\s*", "", raw.upper()).strip(" .$")
        if t in tickers:
            return tickers.index(t), raw
        hits = [j for j, n in enumerate(names) if n["name"].lower() in raw.lower()]
        if len(hits) == 1:
            return hits[0], raw
    return None, raw


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", default="main")
    ap.add_argument("--models", help="comma-separated (default: config models list)")
    ap.add_argument("--runs", type=int, help="runs per condition (default: config)")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true")
    a = ap.parse_args()
    load_dotenv(REPO / ".env")

    cfg, pr = S2.load()
    mcfg_all = yaml.safe_load(open(MODELS))
    keys = a.models.split(",") if a.models else cfg["models"]
    n = a.runs or cfg["runs_per_condition"]
    sha = design_sha()

    jobs = {mk: [(c, i) for c in CONDITIONS for i in range(n)] for mk in keys}
    total = 0
    print(f"Stage 2 phase '{a.phase}', design sha256 {sha[:12]}…, {len(CONDITIONS)} conditions x {n} runs")
    for mk, js in jobs.items():
        path = RAW / f"stage2_{a.phase}_{mk}.jsonl"
        done = {r["run_id"] for r in read_jsonl(path) if not r.get("error")}
        todo = sum(f"{a.phase}|{mk}|{c}|{i:04d}" not in done for c, i in js)
        tin = statistics.mean(sum(len(m["content"]) for m in S2.messages(cfg, pr, i, c)[0]) / 4 + 20 for c, i in js)
        print(f"  {mk:<14} planned {len(js)}  to run {todo}  ~{tin:.0f} tokens in/call  "
              f"~{todo * DEFAULT_SEC_PER_CALL / 60:.0f} min")
        total += todo
    if a.dry_run or total == 0:
        return
    if total > 300 and not a.yes:
        sys.exit("More than 300 calls: re-run with --yes after approval.")

    for mk, js in jobs.items():
        mcfg = mcfg_all["models"][mk]
        if mcfg["provider"] != "ollama":
            sys.exit(f"{mk}: Stage 2 is local-only in this design.")
        digest = check_ollama(mcfg_all, mcfg["model_id"])
        path = RAW / f"stage2_{a.phase}_{mk}.jsonl"
        done = {r["run_id"] for r in read_jsonl(path) if not r.get("error")}
        errors = n_calls = n_fail = 0
        for c, i in js:
            run_id = f"{a.phase}|{mk}|{c}|{i:04d}"
            if run_id in done:
                continue
            msgs, ranks, rows = S2.messages(cfg, pr, i, c)
            names = cfg["companies"] if c == "real_names" else cfg["fictional"]
            seed = stable_seed("own_maker_stage2", c, i)
            res = call_model(mcfg_all, mcfg, msgs, seed)
            slot, raw_ticker = (None, None) if res["error"] else parse_pick(res["raw_response"], names)
            now = datetime.now(timezone.utc)
            rec = {"run_id": run_id, "phase": a.phase, "stage": "stage2", "model_key": mk,
                   "provider": mcfg["provider"], "model_id": mcfg["model_id"], "model_digest": digest,
                   "condition": c, "run_index": i, "seed": seed, "design_sha256": sha,
                   "ranks_by_slot": [ranks[j] for j in range(len(names))], "row_order_slots": rows,
                   "chosen_slot": slot, "chosen_ticker_raw": raw_ticker,
                   "chosen_slot_company": cfg["companies"][slot]["id"] if slot is not None else None,  # real company of that slot
                   "temperature": mcfg_all["defaults"]["params"]["temperature"],
                   "max_tokens": mcfg_all["defaults"]["params"]["max_tokens"],
                   "timestamp": now.isoformat(), "date_utc": now.date().isoformat(), **res}
            with open(path, "a") as f:
                f.write(json.dumps(rec) + "\n")
            errors = errors + 1 if res["error"] else 0
            n_calls += 1
            n_fail += int(bool(res["error"]) or slot is None)
            print(f"{run_id}  {res['latency_ms']} ms  slot={slot} rank={ranks.get(slot) if slot is not None else None}  "
                  f"{'ERR ' + res['error'] if res['error'] else ''}", flush=True)
            if errors >= MAX_CONSECUTIVE_ERRORS:
                sys.exit(f"AUTO-STOP {mk}: {errors} consecutive errors, last: {res['error']}")
            if n_calls >= MIN_CALLS_FOR_RATE and n_fail / n_calls > MAX_FAIL_RATE:
                sys.exit(f"AUTO-STOP {mk}: {n_fail}/{n_calls} calls failed or had no valid ticker.")


if __name__ == "__main__":
    main()
