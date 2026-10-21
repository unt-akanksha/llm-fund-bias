"""Study 1 v2 EXTENSION: OpenAI models (added after the design freeze, tag v2.0-frozen-design, at the
professor's request). Does not touch the frozen local run; reuses its prompts and parsing read-only.

  python src/v2/run_openai.py --list-models         # model IDs starting with "gpt"
  python src/v2/run_openai.py --dry-run-calls       # 3 real calls per model -> runs/raw_v2/openai_dryrun.jsonl
  python src/v2/run_openai.py --pass 1 [--models gpt-5.4-mini]   # Pass 1 cells x 50, then the gate
  python src/v2/run_openai.py --pass 2 [--models ...]            # all 26 cells x 100 (only after a gate PASS)
  python src/v2/run_openai.py --gate [--models ...]
  python src/v2/run_openai.py --cells D2__real,D4__real --runs 50 --cap-usd 2   # add-on cells; gate via analyze.py

Same as local: 26 conditions (data/conditions_v2.csv), render.build_messages, row orders, seeds,
run_main.parse, temperature 1.0 (when accepted). Differences are logged per call (reasoning_effort used,
whether temperature/seed were accepted). The output cap covers reasoning + answer (max_completion_tokens);
a cut-off answer (finish_reason "length") is a failed call.
Spend: the cost of every logged call (reported usage x config prices) plus a worst-case reserve for calls
in flight may never pass spend.cap_usd; otherwise the run aborts before sending.
Log: runs/raw_v2/main_openai.jsonl (append-only, resumable). Every row: extension = true.
The API key is read from .env (OPENAI_API_KEY) and never printed or logged.
"""

import argparse
import json
import random
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from common import read_jsonl, stable_seed  # noqa: E402
from name_id_check import recommended_fund  # noqa: E402

from v2 import render  # noqa: E402
from v2.run_main import FULL_RUNS, GATE_MAX, PASS1, PASS1_RUNS, PHASE, messages_for, name_map, parse  # noqa: E402

CONFIG = ROOT / "config" / "models_v2_openai.yaml"
LOGDIR = ROOT / "runs" / "raw_v2"
LOG = LOGDIR / "main_openai.jsonl"
DRYLOG = LOGDIR / "openai_dryrun.jsonl"
PROGRESS = ROOT / "runs" / "v2_openai_progress.log"
DRY_CELLS = [("baseline__real", 0), ("D1__real", 0), ("W1__real", 0)]
EXTENSION = {"extension": True, "label": "extension, post-freeze",
             "extension_note": "added after the design freeze (v2.0-frozen-design) at the professor's request"}
_lock = threading.Lock()


class SpendCapReached(Exception):
    pass


def api_key():
    for line in open(ROOT / ".env"):
        if line.startswith("OPENAI_API_KEY="):
            return line.split("=", 1)[1].strip().strip("'\"") or None
    return None


def _redact(s):
    return re.sub(r"sk-[A-Za-z0-9_\-*]+", "sk-[REDACTED]", str(s))


def http(method, path, cfg, body=None, timeout=120):
    req = urllib.request.Request(cfg["base_url"] + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": "Bearer " + api_key(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def call_cost(usage, price):
    """USD from reported usage: cached input at the cached rate, output includes reasoning tokens."""
    pin = usage.get("prompt_tokens", 0)
    cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
    out = usage.get("completion_tokens", 0)
    return ((pin - cached) * price["input"] + cached * price["cached_input"] + out * price["output"]) / 1e6


def spent(cfg):
    prices = {m["model_id"]: m["price_per_m"] for m in cfg["models"].values()}
    return sum(r.get("cost_usd") or 0 for p in (LOG, DRYLOG) for r in read_jsonl(p)
               if r.get("model_id") in prices)


class Caller:
    """Finds the lowest accepted reasoning_effort and whether temperature/seed are accepted (per model)."""

    def __init__(self, cfg, mk):
        self.cfg, self.mk = cfg, mk
        self.m = cfg["models"][mk]
        self.settings = None

    def _body(self, messages, seed, s):
        b = {"model": self.m["model_id"], "messages": messages,
             "max_completion_tokens": self.cfg["defaults"]["params"]["max_completion_tokens"]}
        if s.get("reasoning_effort"):
            b["reasoning_effort"] = s["reasoning_effort"]
        if s.get("temperature") is not None:
            b["temperature"] = s["temperature"]
        if s.get("seed"):
            b["seed"] = seed
        return b

    def probe_settings(self, messages, seed):
        """Try settings from closest-to-local downward; the first accepted is kept. Returns (resp, latency)."""
        p = self.cfg["defaults"]["params"]
        trials = [{"reasoning_effort": e, "temperature": t, "seed": sd}
                  for e in p["reasoning_effort_try"] for t in (p["temperature"], None) for sd in (True, False)]
        last = None
        for s in trials:
            try:
                t0 = time.time()
                resp = http("POST", "/chat/completions", self.cfg, self._body(messages, seed, s))
                self.settings = s
                return resp, int((time.time() - t0) * 1000)
            except urllib.error.HTTPError as e:
                last = _redact(e.read().decode()[:300])
                if e.code != 400:
                    raise
        raise RuntimeError(f"no accepted settings for {self.mk}: {last}")

    def call(self, messages, seed):
        if self.settings is None:
            with _lock:
                if self.settings is None:
                    return self.probe_settings(messages, seed)
        delay = 2.0
        for attempt in range(7):
            try:
                t0 = time.time()
                resp = http("POST", "/chat/completions", self.cfg, self._body(messages, seed, self.settings))
                return resp, int((time.time() - t0) * 1000)
            except urllib.error.HTTPError as e:
                if e.code in (429, 500, 502, 503, 504) and attempt < 6:
                    ra = e.headers.get("retry-after")
                    time.sleep(float(ra) if ra and ra.replace(".", "").isdigit() else delay + random.random())
                    delay = min(delay * 2, 60)
                    continue
                raise
            except (urllib.error.URLError, TimeoutError):
                if attempt < 6:
                    time.sleep(delay)
                    delay = min(delay * 2, 60)
                    continue
                raise


def record(cfg, mk, caller, c, i, funds, tickers, masks_rev, pass_name):
    msgs, order = messages_for(c, i, funds, tickers)
    seed = stable_seed("v2", c["condition_id"], i)              # same seed as the local run
    rid = f"{PHASE}|{c['condition_id']}|{i:04d}|{mk}"
    base = {"run_id": rid, "phase": PHASE, "pass": pass_name, "condition_id": c["condition_id"],
            "base_condition": c["base_condition"], "naming": c["naming"], "run_index": i, "model_key": mk,
            "provider": "openai", "model_id": caller.m["model_id"], "seed": seed, "row_order": order,
            "documents": c["documents"], "target_roles": c["target_roles"], "memory": c["memory"], **EXTENSION}
    try:
        resp, ms = caller.call(msgs, seed)
    except Exception as e:  # noqa: BLE001  (logged as a failed call)
        return {**base, "error": _redact(e)[:300], "cost_usd": 0.0, "timestamp": datetime.now(timezone.utc).isoformat()}
    ch = resp["choices"][0]
    u = resp.get("usage", {})
    reasoning_tok = (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0
    text = ch["message"].get("content") or ""
    cutoff = ch.get("finish_reason") == "length"
    chosen, raw, reasoning = (None, None, None) if cutoff else parse(text, c["naming"], masks_rev)
    s = caller.settings
    return {**base, "error": "cutoff_length" if cutoff else None, "finish_reason": ch.get("finish_reason"),
            "raw_response": text, "chosen_ticker": chosen, "chosen_raw": raw, "reasoning": reasoning,
            "tokens_in": u.get("prompt_tokens"),
            "tokens_in_cached": (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0),
            "tokens_out": u.get("completion_tokens"), "tokens_reasoning": reasoning_tok,
            "tokens_answer": (u.get("completion_tokens") or 0) - reasoning_tok,
            "over_local_answer_cap": (u.get("completion_tokens") or 0) - reasoning_tok > cfg["defaults"]["params"]["local_answer_cap"],
            "hit_output_cap": cutoff, "cost_usd": round(call_cost(u, caller.m["price_per_m"]), 8),
            "reasoning_effort": s["reasoning_effort"], "temperature_sent": s["temperature"],
            "seed_sent": bool(s["seed"]), "max_completion_tokens": cfg["defaults"]["params"]["max_completion_tokens"],
            "system_fingerprint": resp.get("system_fingerprint"), "response_model": resp.get("model"),
            "latency_ms": ms, "timestamp": datetime.now(timezone.utc).isoformat()}


def worst_case_usd(cfg, mk, n_in_tokens=3000):
    p = cfg["models"][mk]["price_per_m"]
    return (n_in_tokens * p["input"] + cfg["defaults"]["params"]["max_completion_tokens"] * p["output"]) / 1e6


def log_progress(msg):
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {msg}"
    with open(PROGRESS, "a") as f:
        f.write(line + "\n")
    print(line, flush=True)


def run_jobs(cfg, mk, jobs, path, pass_name, run_cap=None, run_base=0.0):
    """jobs: [(condition row, run index)]. Concurrency <= cfg concurrency; spend-capped; append to path."""
    funds = render.load_funds(render.FILLED_CSV, placeholder=False)
    tickers = [f["ticker"] for f in funds]
    masks_rev = {code: t for t, (code, _) in render.mask_map(tickers).items()}
    caller = Caller(cfg, mk)
    cap, reserve = cfg["spend"]["cap_usd"], worst_case_usd(cfg, mk)
    state = {"spent": spent(cfg), "inflight": 0, "n": 0, "bad": 0, "stop": None}
    last_status = [time.time()]

    def one(job):
        c, i = job
        with _lock:
            if state["stop"]:
                return
            if state["spent"] + (state["inflight"] + 1) * reserve > cap:
                state["stop"] = f"spend cap: ${state['spent']:.4f} spent + in-flight reserve would pass ${cap:.2f}"
                return
            elif run_cap is not None and state["spent"] - run_base + (state["inflight"] + 1) * reserve > run_cap:
                state["stop"] = (f"spend cap (this run): ${state['spent'] - run_base:.4f} spent + in-flight reserve "
                                 f"would pass ${run_cap:.2f}")
                return
            state["inflight"] += 1
        rec = record(cfg, mk, caller, c, i, funds, tickers, masks_rev, pass_name)
        with _lock:
            state["inflight"] -= 1
            state["spent"] += rec.get("cost_usd") or 0
            state["n"] += 1
            state["bad"] += int(bool(rec["error"]) or rec.get("chosen_ticker") not in tickers)
            with open(path, "a") as f:
                f.write(json.dumps(rec) + "\n")
            if state["n"] >= 40 and state["bad"] / state["n"] > 0.05:
                state["stop"] = f"{state['bad']}/{state['n']} calls failed or invalid (> 5%)"
            if time.time() - last_status[0] >= 15 * 60:
                log_progress(f"STATUS {pass_name} {mk}: {state['n']}/{len(jobs)}, failed-or-invalid {state['bad']}, "
                             f"spent ${state['spent']:.4f}")
                last_status[0] = time.time()

    if jobs:  # first call alone, so the accepted settings are probed once
        one(jobs[0])
    with ThreadPoolExecutor(max_workers=min(3, cfg["concurrency"])) as ex:
        list(ex.map(one, jobs[1:]))
    if state["stop"]:
        log_progress(f"AUTO-STOP {mk}: {state['stop']}")
        raise SpendCapReached(state["stop"]) if state["stop"].startswith("spend cap") else SystemExit(3)
    log_progress(f"{pass_name} {mk}: finished {state['n']} calls, spent so far ${state['spent']:.4f}")
    return caller.settings


def gate(models):
    """Same rules as the local Pass 1 gate incl. Amendment 1 (invalid tickers flagged, not a stop).
    Cut-off answers count as cap hits and are not completed."""
    funds = render.load_funds(render.FILLED_CSV, placeholder=False)
    valid = {f["ticker"] for f in funds}
    conds = {c["condition_id"]: c for c in render.load_conditions()}
    lines, fails, pool = [], [], []
    rows = read_jsonl(LOG)
    for mk in models:
        for cid in PASS1:
            att = [r for r in rows if r["model_key"] == mk and r["condition_id"] == cid and r["run_index"] < PASS1_RUNS]
            ok = {r["run_id"]: r for r in att if not r.get("error")}.values()
            n = len(ok)
            cut = sum(1 for r in att if r.get("hit_output_cap"))
            invalid = sum(1 for r in ok if r["chosen_ticker"] not in valid)
            names = name_map(funds, conds[cid]["naming"])
            cls = mism = 0
            for r in ok:
                if r["chosen_ticker"] in valid:
                    t, _ = recommended_fund(r.get("reasoning") or "", names)
                    if t:
                        cls += 1
                        mism += int(t != r["chosen_ticker"])
            picks = Counter(r["chosen_ticker"] for r in ok if r["chosen_ticker"] in valid)
            share_sum = sum(v / sum(picks.values()) for v in picks.values()) if picks else 0.0
            checks = {"planned=completed": n == PASS1_RUNS, "name-vs-ID<=2%": (mism / cls if cls else 0) <= GATE_MAX,
                      "cap/cut-off<=2%": cut / PASS1_RUNS <= GATE_MAX, "shares sum to 1": abs(share_sum - 1) < 1e-9}
            lines.append(f"{mk:<13} {cid:<18} n={n:<3} name/ID {mism}/{cls} | invalid (flagged) {invalid} | cut-off {cut} | "
                         + " ".join(f"{k}:{'PASS' if v else 'FAIL'}" for k, v in checks.items()))
            fails += [f"{mk} {cid}: {k}" for k, v in checks.items() if not v]
            pool += list(ok)
    sample = random.Random(20261020).sample(sorted(pool, key=lambda r: r["run_id"]), min(20, len(pool)))
    with open(ROOT / "runs" / "v2_openai_pass1_sample.txt", "w") as f:
        for r in sample:
            f.write(f"--- {r['run_id']} (chosen {r['chosen_ticker']})\n{r['raw_response']}\n\n")
    verdict = "PASS" if not fails else "FAIL: " + "; ".join(fails)
    (ROOT / "runs" / "v2_openai_gate_pass1.txt").write_text("\n".join(lines) + f"\n\nGATE PASS 1: {verdict}\n")
    log_progress(f"GATE PASS 1 (openai): {verdict}")
    return not fails


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default="gpt-5.4-mini,gpt-5.4")
    ap.add_argument("--list-models", action="store_true")
    ap.add_argument("--dry-run-calls", action="store_true")
    ap.add_argument("--pass", dest="pass_no", type=int, choices=(1, 2))
    ap.add_argument("--gate", action="store_true")
    ap.add_argument("--cells", help="add-on: comma-separated condition IDs (with --runs); no runner gate, use analyze.py")
    ap.add_argument("--runs", type=int, default=50)
    ap.add_argument("--cap-usd", type=float, help="spend cap for this invocation (the global cap still applies)")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(CONFIG))
    print("key found: " + ("yes" if api_key() else "no"))
    models = a.models.split(",")
    if a.list_models:
        print("\n".join(sorted(m["id"] for m in http("GET", "/models", cfg)["data"] if m["id"].startswith("gpt"))))
        return
    if a.gate:
        sys.exit(0 if gate(models) else 1)
    conds = {c["condition_id"]: c for c in render.load_conditions() if c["block"] in ("core", "order")}
    LOGDIR.mkdir(parents=True, exist_ok=True)
    if a.dry_run_calls:
        for mk in models:
            run_jobs(cfg, mk, [(conds[c], i) for c, i in DRY_CELLS], DRYLOG, "dryrun")
        return
    if a.cells:
        cells = a.cells.split(",")
        assert all(c in conds for c in cells), cells
        done = {r["run_id"] for r in read_jsonl(LOG) if not r.get("error")}
        base = spent(cfg)
        for mk in models:
            jobs = [(conds[c], i) for i in range(a.runs) for c in cells if f"{PHASE}|{c}|{i:04d}|{mk}" not in done]
            log_progress(f"ADDON {mk}: {len(jobs)} calls to run ({','.join(cells)} x {a.runs}); "
                         f"spent so far ${spent(cfg):.4f}; this run cap ${a.cap_usd}")
            run_jobs(cfg, mk, jobs, LOG, "ADDON", a.cap_usd, base)
        return
    if a.pass_no:
        cells, n_runs = (PASS1, PASS1_RUNS) if a.pass_no == 1 else (list(conds), FULL_RUNS)
        done = {r["run_id"] for r in read_jsonl(LOG) if not r.get("error")}
        for mk in models:
            jobs = [(conds[c], i) for i in range(n_runs) for c in cells
                    if f"{PHASE}|{c}|{i:04d}|{mk}" not in done]
            log_progress(f"PASS{a.pass_no} {mk}: {len(jobs)} calls to run; spent so far ${spent(cfg):.4f}")
            run_jobs(cfg, mk, jobs, LOG, f"PASS{a.pass_no}")
        if a.pass_no == 1:
            sys.exit(0 if gate(models) else 1)


if __name__ == "__main__":
    main()
