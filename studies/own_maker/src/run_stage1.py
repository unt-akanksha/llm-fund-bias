"""Own-maker study, Stage 1: stock-suggestion runs (and the one-time maker question).

  python studies/own_maker/src/run_stage1.py --dry-run                    # plan, calls, token estimate
  python studies/own_maker/src/run_stage1.py --phase smoke --runs-per-prompt 1 --yes
  python studies/own_maker/src/run_stage1.py                              # main: all enabled models
  python studies/own_maker/src/run_stage1.py --maker-question             # one call per model, context only

Logs: studies/own_maker/runs/raw/stage1_<phase>_<model_key>.jsonl (append-only). Re-running resumes:
run_ids with a successful response are skipped. Every record carries provider, model id and UTC date.
Groq limits (requests/tokens per minute and per day) come from config/models.yaml; 429s are retried
with Retry-After plus exponential backoff (src/providers.py, shared with the fund study).
"""

import argparse
import hashlib
import json
import statistics
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv

STUDY = Path(__file__).resolve().parent.parent
REPO = STUDY.parent.parent
sys.path.insert(0, str(REPO / "src"))
from common import read_jsonl, stable_seed  # noqa: E402  (repo src/, unchanged)
import providers  # noqa: E402
from providers import MinuteThrottle, call_model, check_groq, check_ollama  # noqa: E402

from companies import companies_in  # noqa: E402

CONFIG = STUDY / "config" / "models.yaml"
PROMPTS = STUDY / "prompts" / "stage1_prompts.yaml"
RAW = STUDY / "runs" / "raw"
CONFIRM_ABOVE = 300
DEFAULT_SEC_PER_CALL = 15.0   # local; replaced by measured latency once logs exist
DEFAULT_TOKENS_OUT = 250      # replaced by measured output tokens once logs exist
MAX_CONSECUTIVE_ERRORS = 3    # e.g. Ollama not responding (each call already retries with backoff)
MAX_FAIL_RATE = 0.05          # auto-stop: (API errors + responses with no parsed stock) / calls this session
MIN_CALLS_FOR_RATE = 40       # ...checked once at least this many calls have been made for the model


# Keep every HTTP response of the current call so Groq-only fields (finish_reason, reasoning tokens,
# x-ratelimit-* headers of each attempt, including retried 429s) can be logged without changing the
# shared src/providers.py.
_LAST = {}
_post = providers.requests.post


def _recording_post(*args, **kwargs):
    r = _post(*args, **kwargs)
    _LAST["r"] = r
    _LAST.setdefault("attempts", []).append(r)
    return r


def ratelimit_headers(r):
    return {k.lower(): v for k, v in r.headers.items()
            if k.lower().startswith("x-ratelimit") or k.lower() == "retry-after"}


providers.requests.post = _recording_post


def groq_extras():
    """finish_reason and reasoning-token count from the last Groq response (None if not reported)."""
    try:
        body = _LAST["r"].json()
    except Exception:  # noqa: BLE001  (no response / not JSON)
        return {"finish_reason": None, "reasoning_tokens": None}
    choice = (body.get("choices") or [{}])[0]
    details = (body.get("usage") or {}).get("completion_tokens_details") or {}
    return {"finish_reason": choice.get("finish_reason"), "reasoning_tokens": details.get("reasoning_tokens")}


def groq_ratelimit_log():
    """[{status, headers}] for every attempt of the current call (429s first, final response last)."""
    return [{"status": r.status_code, "headers": ratelimit_headers(r)} for r in _LAST.get("attempts", [])]


def load_yaml(p):
    with open(p) as f:
        return yaml.safe_load(f)


def prompts_sha256():
    return hashlib.sha256(PROMPTS.read_bytes()).hexdigest()


def messages_for(text, suffix):
    return [{"role": "user", "content": f"{text}\n\n{suffix}"}]


def log_path(phase, mk):
    return RAW / f"stage1_{phase}_{mk}.jsonl"


def done_ids(path):
    return {r["run_id"] for r in read_jsonl(path) if not r.get("error")}


def measured(mk, field):
    """Median of a logged field over all Stage 1 logs for this model (any phase), or None."""
    vals = [r[field] for p in RAW.glob(f"stage1_*_{mk}.jsonl") if not p.name.startswith("stage1_maker_")
            for r in read_jsonl(p) if not r.get("error") and r.get(field) is not None]
    return statistics.median(vals) if vals else None


def calls_last_24h(path):
    cutoff = datetime.now(timezone.utc) - timedelta(days=1)
    recs = [r for r in read_jsonl(path) if datetime.fromisoformat(r["timestamp"]) > cutoff]
    return len(recs), sum((r.get("tokens_in") or 0) + (r.get("tokens_out") or 0) for r in recs)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--phase", default="main")
    ap.add_argument("--models", help="comma-separated model keys (default: all enabled)")
    ap.add_argument("--prompts", help="comma-separated prompt ids (default: all 10)")
    ap.add_argument("--runs-per-prompt", type=int)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--yes", action="store_true", help=f"skip confirmation above {CONFIRM_ABOVE} calls")
    ap.add_argument("--max-calls-per-day", type=int, help="stop cleanly after this many calls in 24 h (per model)")
    ap.add_argument("--maker-question", action="store_true", help="ask each model once who made it; then exit")
    a = ap.parse_args()

    load_dotenv(REPO / ".env")
    cfg, pr = load_yaml(CONFIG), load_yaml(PROMPTS)
    keys = a.models.split(",") if a.models else [k for k, m in cfg["models"].items() if m.get("enabled")]
    unknown = set(keys) - set(cfg["models"])
    if unknown:
        sys.exit(f"Unknown model keys: {unknown}")
    pids = a.prompts.split(",") if a.prompts else list(pr["prompts"])
    n = a.runs_per_prompt or cfg["stage1_runs_per_prompt"]
    sha = prompts_sha256()

    if a.maker_question:
        jobs = {mk: [("maker_question", 0, [{"role": "user", "content": pr["maker_question"]}])] for mk in keys}
        phase = "maker"
    else:
        jobs = {mk: [(pid, i, messages_for(pr["prompts"][pid], pr["output_suffix"])) for pid in pids for i in range(n)]
                for mk in keys}
        phase = a.phase

    # ---- plan / dry run
    plan, total = [], 0
    for mk, js in jobs.items():
        path = log_path(phase, mk)
        done = done_ids(path)
        todo = [j for j in js if f"{phase}|{mk}|{j[0]}|{j[1]:04d}" not in done]
        tin = statistics.mean(sum(len(m["content"]) for m in j[2]) / 4 + 10 for j in js)  # ~4 chars/token
        tout = measured(mk, "tokens_out") or DEFAULT_TOKENS_OUT
        tin_m = measured(mk, "tokens_in")
        sec = (measured(mk, "latency_ms") or DEFAULT_SEC_PER_CALL * 1000) / 1000
        plan.append((mk, len(js), len(todo), tin_m or tin, tin_m is not None, tout, sec))
        total += len(todo)
    print(f"Phase '{phase}', prompts sha256 {sha[:12]}…, {len(pids)} prompt(s) x {n} run(s)")
    print(f"{'model':<14}{'planned':>8}{'to run':>8}{'tok_in/call':>13}{'tok_out/call':>14}{'tok_total':>11}{'est. time':>11}")
    for mk, planned, todo, tin, tin_measured, tout, sec in plan:
        prov = cfg["models"][mk]["provider"]
        t = f"{todo * sec / 3600:.1f} h" if prov == "ollama" else "rate-limited"
        print(f"{mk:<14}{planned:>8}{todo:>8}{tin:>12.0f}{'' if tin_measured else '*':1}{tout:>13.0f}"
              f"{'' if measured(mk, 'tokens_out') else '*':1}{todo * (tin + tout):>11.0f}{t:>11}")
    print("* = estimate (no logged calls yet); otherwise median of logged calls")
    if a.dry_run or total == 0:
        return
    if total > CONFIRM_ABOVE and not a.yes:
        if input(f"About to make {total} calls. Continue? [y/N] ").strip().lower() != "y":
            sys.exit("Aborted.")

    # ---- run
    RAW.mkdir(parents=True, exist_ok=True)
    for mk, js in jobs.items():
        mcfg = cfg["models"][mk]
        digest = check_ollama(cfg, mcfg["model_id"]) if mcfg["provider"] == "ollama" else check_groq(cfg, mcfg)
        lim = mcfg.get("limits") or {}
        throttle = MinuteThrottle(lim["requests_per_min"], lim["tokens_per_min"]) if mcfg["provider"] == "groq" else None
        path = log_path(phase, mk)
        done = done_ids(path)
        errors = n_calls = n_fail = 0
        for pid, i, msgs in js:
            run_id = f"{phase}|{mk}|{pid}|{i:04d}"
            if run_id in done:
                continue
            calls24, tok24 = calls_last_24h(path)
            caps = [c for c in (a.max_calls_per_day, lim.get("requests_per_day")) if c]
            if caps and calls24 >= min(caps):
                print(f"{mk}: daily call cap reached ({calls24}); stopping. Re-run later to resume.")
                break
            if lim.get("tokens_per_day") and tok24 >= lim["tokens_per_day"]:
                print(f"{mk}: daily token cap reached ({tok24}); stopping. Re-run later to resume.")
                break
            seed = stable_seed("own_maker_stage1", pid, i)
            max_tokens = {**cfg["defaults"]["params"], **mcfg.get("params", {})}["max_tokens"]
            if throttle:
                throttle.wait(max_tokens + 100)
            _LAST.clear()
            res = call_model(cfg, mcfg, msgs, seed)
            if mcfg["provider"] == "groq":
                res.update(groq_extras())
                res["ratelimit_attempts"] = groq_ratelimit_log()
            if throttle:
                throttle.record((res["tokens_in"] or 0) + (res["tokens_out"] or 0))
            now = datetime.now(timezone.utc)
            rec = {"run_id": run_id, "phase": phase, "stage": "stage1", "model_key": mk,
                   "provider": mcfg["provider"], "model_id": mcfg["model_id"], "model_digest": digest,
                   "prompt_id": pid, "prompts_sha256": sha, "run_index": i, "seed": seed,
                   "temperature": cfg["defaults"]["params"]["temperature"],
                   "max_tokens": max_tokens,
                   "timestamp": now.isoformat(), "date_utc": now.date().isoformat(), **res}
            with open(path, "a") as f:
                f.write(json.dumps(rec) + "\n")
            errors = errors + 1 if res["error"] else 0
            parsed = 0 if res["error"] else len(companies_in(res["raw_response"]))
            n_calls += 1
            n_fail += int(bool(res["error"]) or parsed == 0)
            extra = f"finish={res.get('finish_reason')} reasoning_tok={res.get('reasoning_tokens')}  " \
                if mcfg["provider"] == "groq" else ""
            print(f"{run_id}  {res['latency_ms']} ms  parsed={parsed}  {extra}"
                  f"{'ERR ' + res['error'] if res['error'] else ''}", flush=True)
            if errors >= MAX_CONSECUTIVE_ERRORS:
                sys.exit(f"AUTO-STOP {mk}: {errors} consecutive errors (provider not responding?), "
                         f"last: {res['error']}")
            if n_calls >= MIN_CALLS_FOR_RATE and n_fail / n_calls > MAX_FAIL_RATE:
                sys.exit(f"AUTO-STOP {mk}: {n_fail}/{n_calls} calls failed or parsed no stock "
                         f"(> {MAX_FAIL_RATE:.0%}). Inspect the log before resuming.")


if __name__ == "__main__":
    main()
