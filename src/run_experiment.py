"""Run the fund-choice experiment.

Examples:
  python src/run_experiment.py --dry-run
  python src/run_experiment.py --phase smoke --models llama3.1-8b --conditions baseline,src_all,mem_pos --runs-per-condition 1
  python src/run_experiment.py --pilot
  python src/run_experiment.py --models llama3.1-8b,qwen2.5-7b        # core conditions, main phase

Each call is appended to runs/raw/<phase>_<model_key>.jsonl. Re-running the same command
resumes: run_ids that already have a successful response are skipped.
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

from common import (DATA, RAW_DIR, build_messages, completed_run_ids, load_conditions, load_config,
                    load_grid, make_run_id, parse_response, plan_run, read_jsonl, stable_seed)
from providers import MinuteThrottle, call_model, check_groq, check_ollama

CONFIRM_ABOVE = 300           # ask before launching more calls than this
DEFAULT_SEC_PER_CALL = 6.0    # used by --dry-run until real latencies are logged
MAX_CONSECUTIVE_ERRORS = 10


def parse_args():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pilot", action="store_true", help="pilot: llama3.1-8b, baseline, 50 runs")
    ap.add_argument("--phase", default="main", help="label for log file and run_ids (main/pilot/smoke)")
    ap.add_argument("--dry-run", action="store_true", help="print plan and estimates; make no calls")
    ap.add_argument("--models", help="comma-separated model keys (default: all enabled)")
    ap.add_argument("--conditions", help="comma-separated condition ids (default: core conditions)")
    ap.add_argument("--runs-per-condition", type=int, help="override per-model setting")
    ap.add_argument("--grid", default="grid", help="grid file stem in data/ (default: grid)")
    ap.add_argument("--max-calls-per-day", type=int, help="stop cleanly after this many calls in 24 h (per model)")
    ap.add_argument("--yes", action="store_true", help=f"skip confirmation for batches > {CONFIRM_ABOVE} calls")
    a = ap.parse_args()
    if a.pilot:
        a.phase = "pilot"
        a.models = a.models or "llama3.1-8b"
        a.conditions = a.conditions or "baseline"
        a.runs_per_condition = a.runs_per_condition or 50
    return a


def log_path(phase, model_key):
    return RAW_DIR / f"{phase}_{model_key}.jsonl"


def build_jobs(args, cfg, grid, conditions):
    """List of (model_key, run_spec) for every planned call, before resume filtering."""
    if args.models:
        model_keys = args.models.split(",")
        unknown = set(model_keys) - set(cfg["models"])
        if unknown:
            sys.exit(f"Unknown model keys: {unknown}. Known: {list(cfg['models'])}")
    else:
        model_keys = [k for k, m in cfg["models"].items() if m.get("enabled")]

    if args.conditions:
        cond_ids = args.conditions.split(",")
        unknown = set(cond_ids) - set(conditions.condition_id)
        if unknown:
            sys.exit(f"Unknown conditions: {unknown}")
        conds = conditions.set_index("condition_id").loc[cond_ids].reset_index()
    else:
        conds = conditions[conditions.core == 1]

    fund_ids = list(grid.fund_id)
    jobs = []
    for mk in model_keys:
        n = args.runs_per_condition or cfg["models"][mk]["runs_per_condition"]
        for _, c in conds.iterrows():
            for i in range(n):
                grid_order, sources = plan_run(args.phase, args.grid, c, i, fund_ids)
                run_id = make_run_id(args.phase, mk, args.grid, c.condition_id, i)
                jobs.append((mk, {
                    "run_id": run_id, "condition_id": c.condition_id, "i": i,
                    "grid_order": grid_order, "sources_in_order": sources,
                    "memory": c.memory or None, "seed": stable_seed("api", run_id),
                }))
    return model_keys, jobs


def calls_in_last_24h(model_key):
    """Calls (any phase, including errors) made for this model in the last 24 h, oldest first."""
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    times = []
    for f in RAW_DIR.glob(f"*_{model_key}.jsonl"):
        for r in read_jsonl(f):
            t = datetime.fromisoformat(r["timestamp"])
            if t > cutoff:
                times.append(t)
    return sorted(times)


def mean_logged_latency_s(model_key):
    lat = [r["latency_ms"] for f in RAW_DIR.glob(f"*_{model_key}.jsonl") for r in read_jsonl(f)
           if not r.get("error") and r.get("latency_ms")]
    return (sum(lat) / len(lat) / 1000) if lat else None


def dry_run(args, cfg, grid, model_keys, todo):
    print(f"\nDRY RUN (phase={args.phase}, grid={args.grid}). No calls made.\n")
    total_calls = total_secs = 0
    for mk in model_keys:
        jobs = [j for m, j in todo if m == mk]
        m = cfg["models"][mk]
        max_out = {**cfg["defaults"]["params"], **m.get("params", {})}["max_tokens"]
        est_in = sum(len(" ".join(x["content"] for x in build_messages(
            grid, j["grid_order"], j["sources_in_order"], j["memory"]))) / 4 for j in jobs)
        est_out = len(jobs) * 120  # typical JSON answer; max_tokens caps it at max_out
        logged = mean_logged_latency_s(mk)
        spc = logged or DEFAULT_SEC_PER_CALL
        secs = len(jobs) * spc
        print(f"{mk} ({m['provider']}:{m['model_id']})")
        print(f"  calls to make : {len(jobs)}")
        print(f"  est. tokens   : ~{est_in:,.0f} in + ~{est_out:,} out (max {len(jobs) * max_out:,} out)")
        if m["provider"] == "groq":
            lim = m.get("limits", {})
            if None in lim.values():
                print("  Groq limits not filled in; cannot estimate days.")
            else:
                days = max(len(jobs) / lim["requests_per_day"], (est_in + est_out) / lim["tokens_per_day"])
                mins = max(len(jobs) / lim["requests_per_min"], (est_in + est_out) / lim["tokens_per_min"])
                print(f"  est. time     : >= {mins:.0f} min of throttled calls, spread over ~{days:.1f} day(s)")
        else:
            src = "from logged latencies" if logged else "default guess, refine after smoke test"
            print(f"  est. time     : ~{secs / 60:.0f} min ({spc:.1f} s/call, {src})")
            total_secs += secs
        total_calls += len(jobs)
    print(f"\nTOTAL calls: {total_calls}" + (f"; local wall-clock ~{total_secs / 3600:.1f} h" if total_secs else ""))


def run_model(args, cfg, grid, mk, jobs):
    m = cfg["models"][mk]
    digest = check_ollama(cfg, m["model_id"]) if m["provider"] == "ollama" else check_groq(cfg, m)
    params = {**cfg["defaults"]["params"], **m.get("params", {})}
    valid_ids = set(grid.fund_id)
    dominant = grid.loc[grid.is_dominant == "1", "fund_id"].iloc[0]

    throttle, daily_cap = None, args.max_calls_per_day
    if m["provider"] == "groq":
        lim = m["limits"]
        throttle = MinuteThrottle(lim["requests_per_min"], lim["tokens_per_min"])
        daily_cap = min(daily_cap or lim["requests_per_day"], lim["requests_per_day"])
    recent = calls_in_last_24h(mk) if daily_cap else []

    path = log_path(args.phase, mk)
    path.parent.mkdir(parents=True, exist_ok=True)
    done = errors = n429 = consecutive_err = 0
    print(f"\n{mk}: {len(jobs)} calls -> {path.relative_to(Path.cwd()) if path.is_relative_to(Path.cwd()) else path}")

    for j in jobs:
        if daily_cap and len(recent) >= daily_cap:
            resume_at = recent[-daily_cap] + timedelta(hours=24)
            print(f"\nDaily cap of {daily_cap} calls reached for {mk}. Progress is saved.")
            print(f"Resume after {resume_at.astimezone():%Y-%m-%d %H:%M %Z} by re-running the same command.")
            return False

        messages = build_messages(grid, j["grid_order"], j["sources_in_order"], j["memory"])
        if throttle:
            est = sum(len(x["content"]) for x in messages) // 4 + params["max_tokens"]
            throttle.wait(est)

        res = call_model(cfg, m, messages, j["seed"])
        if throttle:
            throttle.record((res["tokens_in"] or 0) + (res["tokens_out"] or 0))

        fund, reasoning, method = parse_response(res["raw_response"], valid_ids)
        record = {
            "run_id": j["run_id"], "phase": args.phase, "model_key": mk,
            "provider": m["provider"], "model": m["model_id"], "model_digest": digest,
            "reasoning_effort": m.get("reasoning_effort"),
            "grid_file": args.grid, "condition_id": j["condition_id"], "run_index": j["i"],
            "sources_in_order": j["sources_in_order"],
            "ratings_position": (j["sources_in_order"].index("src_ratings") + 1
                                 if "src_ratings" in j["sources_in_order"] else None),
            "memory": j["memory"], "grid_order": j["grid_order"],
            "dominant_position": j["grid_order"].index(dominant) + 1,
            "temperature": params["temperature"], "max_tokens": params["max_tokens"], "seed": j["seed"],
            "chosen_fund": fund,
            "chosen_position": j["grid_order"].index(fund) + 1 if fund else None,
            "chose_dominant": (fund == dominant) if fund else None,
            "parse_method": method, "reasoning_text": reasoning, "raw_response": res["raw_response"],
            "tokens_in": res["tokens_in"], "tokens_out": res["tokens_out"], "latency_ms": res["latency_ms"],
            "http_status": res["http_status"], "retries": res["retries"],
            "timestamp": datetime.now(timezone.utc).isoformat(), "error": res["error"],
        }
        with open(path, "a") as f:  # append-only
            f.write(json.dumps(record) + "\n")
        recent.append(datetime.now(timezone.utc))

        done += 1
        n429 += res["n429"]
        if res["error"]:
            errors += 1
            consecutive_err += 1
            if consecutive_err >= MAX_CONSECUTIVE_ERRORS:
                print(f"\n{MAX_CONSECUTIVE_ERRORS} errors in a row; stopping. Last error: {res['error']}")
                return False
        else:
            consecutive_err = 0
        print(f"\r  done {done}/{len(jobs)} | remaining {len(jobs) - done} | errors {errors} | 429s {n429}",
              end="", flush=True)
    print()
    return True


def main():
    load_dotenv()
    args = parse_args()
    cfg = load_config()
    grid = load_grid(DATA / f"{args.grid}.csv")
    conditions = load_conditions()

    model_keys, jobs = build_jobs(args, cfg, grid, conditions)
    done_ids = {mk: completed_run_ids(log_path(args.phase, mk)) for mk in model_keys}
    todo = [(mk, j) for mk, j in jobs if j["run_id"] not in done_ids[mk]]
    skipped = len(jobs) - len(todo)
    if skipped:
        print(f"Resuming: {skipped} of {len(jobs)} runs already done, skipping them.")

    if args.dry_run:
        dry_run(args, cfg, grid, model_keys, todo)
        return
    if not todo:
        print("Nothing to do.")
        return
    if len(todo) > CONFIRM_ABOVE and not args.yes:
        if input(f"About to make {len(todo)} calls. Continue? [y/N] ").strip().lower() != "y":
            sys.exit("Aborted.")

    for mk in model_keys:
        model_jobs = [j for m, j in todo if m == mk]
        if model_jobs and not run_model(args, cfg, grid, mk, model_jobs):
            sys.exit(1)
    print("All done.")


if __name__ == "__main__":
    main()
