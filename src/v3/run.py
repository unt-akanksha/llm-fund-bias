"""Study 1 v3 runner: OpenAI, Anthropic and local Ollama models (docs/design_v3.md).

  python src/v3/run.py --keys                          # "key found: yes/no" per vendor; lists model IDs
  python src/v3/run.py --pilot --models gpt-5.4-nano   # 4 cells x 1 run -> runs/raw_v3/pilot_<model>.jsonl
  python src/v3/run.py --models gpt-5.4-nano,gpt-5.4-mini --runs 30   # full run (Amendment v3-1: 30 for API)

Writes ONLY under runs/raw_v3/ (append-only, resumable by run_id). Never touches v2 files.
Spend: each vendor has a hard cap over all v3 calls (pilot + main) from the usage the API reports, plus a
worst-case reserve for calls in flight; the run stops before passing it. Keys are read from .env, never
printed or logged. Auto-stop: 3 consecutive errors, or > 5% failed/invalid after 40 calls.
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
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from common import read_jsonl  # noqa: E402
from providers import call_model as ollama_call, check_ollama  # noqa: E402

from v3 import prompts  # noqa: E402

CONFIG = ROOT / "config" / "models_v3.yaml"
LOGDIR = ROOT / "runs" / "raw_v3"
PROGRESS = ROOT / "runs" / "v3_progress.log"
PILOT_CELLS = ["sp500|baseline|A|standard", "sp500|D5|B|fiduciary", "ndx|D7|A|fiduciary", "ndx|D1|B|standard"]
LABEL = {"study": "v3", "design_tag": "v3.0-frozen-design"}
_lock = threading.Lock()


# ---------------- keys (never printed) ----------------

def env_key(name):
    p = ROOT / ".env"
    if not p.exists():
        return None
    for line in open(p):
        if line.startswith(name + "="):
            return line.split("=", 1)[1].strip().strip("'\"") or None
    return None


def _redact(s):
    return re.sub(r"(sk-[A-Za-z0-9_\-*]+|sk-ant-[A-Za-z0-9_\-*]+)", "[REDACTED]", str(s))


def safe_log_path(path):
    path = Path(path).resolve()
    if LOGDIR.resolve() not in path.parents:
        raise ValueError(f"refusing to write outside {LOGDIR}: {path}")
    return path


# ---------------- parsing (v2 parser; v3 adds only markdown-fence stripping) ----------------

FENCE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.S)


def parse(text, valid):
    """-> (chosen ticker or None, raw ticker, reasoning, fence_stripped). Same rules as v2 run_main.parse,
    after removing a surrounding ```json ... ``` fence if the model added one."""
    if text is None:
        return None, None, None, False
    m = FENCE.match(text)
    stripped = bool(m)
    if m:
        text = m.group(1)
    try:
        obj = json.loads(text)
        raw = str(obj.get("ticker", "")).strip().upper()
        reasoning = obj.get("reasoning")
    except (json.JSONDecodeError, TypeError, AttributeError):
        return None, None, None, stripped
    raw = re.sub(r"^(NYSE|NASDAQ|NYSEARCA)\s*:\s*", "", raw)
    return (raw if raw in valid else raw or None), raw, reasoning, stripped


# ---------------- API clients ----------------

def _post(url, body, headers, timeout=120):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), method="POST",
                                 headers={"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def _get(url, headers, timeout=30):
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=timeout) as r:
        return json.load(r)


def with_backoff(fn):
    delay = 2.0
    for attempt in range(7):
        try:
            return fn()
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504, 529) and attempt < 6:
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


class OpenAIClient:
    def __init__(self, cfg, m):
        self.cfg, self.m, self.p = cfg, m, cfg["defaults"]["params"]
        self.key = env_key(cfg["providers"]["openai"]["api_key_env"])
        self.base = cfg["providers"]["openai"]["base_url"]
        self.settings = None

    def _body(self, messages, seed, s):
        b = {"model": self.m["model_id"], "messages": messages, "max_completion_tokens": self.p["api_max_output"]}
        if s["reasoning_effort"]:
            b["reasoning_effort"] = s["reasoning_effort"]
        if s["temperature"] is not None:
            b["temperature"] = s["temperature"]
        if s["seed"]:
            b["seed"] = seed
        return b

    def _send(self, messages, seed, s):
        return _post(f"{self.base}/chat/completions", self._body(messages, seed, s),
                     {"Authorization": "Bearer " + self.key})

    def call(self, messages, seed):
        if self.settings is None:
            with _lock:
                if self.settings is None:
                    last = None
                    for s in [{"reasoning_effort": e, "temperature": t, "seed": sd}
                              for e in self.p["reasoning_effort_try"] for t in (self.p["temperature"], None)
                              for sd in (True, False)]:
                        try:
                            resp = with_backoff(lambda: self._send(messages, seed, s))
                            self.settings = s
                            return self._out(resp)
                        except urllib.error.HTTPError as e:
                            last = _redact(e.read().decode()[:300])
                            if e.code != 400:
                                raise
                    raise RuntimeError(f"no accepted settings: {last}")
        return self._out(with_backoff(lambda: self._send(messages, seed, self.settings)))

    def _out(self, resp):
        ch = resp["choices"][0]
        u = resp.get("usage", {})
        cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0) or 0
        reas = (u.get("completion_tokens_details") or {}).get("reasoning_tokens", 0) or 0
        pr = self.m["price_per_m"]
        cost = ((u.get("prompt_tokens", 0) - cached) * pr["input"] + cached * pr["cached_input"]
                + u.get("completion_tokens", 0) * pr["output"]) / 1e6
        s = self.settings or {}
        return {"raw_response": ch["message"].get("content"), "finish_reason": ch.get("finish_reason"),
                "cutoff": ch.get("finish_reason") == "length", "tokens_in": u.get("prompt_tokens"),
                "tokens_in_cached": cached, "tokens_out": u.get("completion_tokens"), "tokens_reasoning": reas,
                "cost_usd": round(cost, 8), "reasoning_effort": s.get("reasoning_effort"),
                "temperature_sent": s.get("temperature"), "seed_sent": bool(s.get("seed")),
                "response_model": resp.get("model"), "system_fingerprint": resp.get("system_fingerprint")}

    def list_models(self):
        return sorted(m["id"] for m in _get(f"{self.base}/models", {"Authorization": "Bearer " + self.key})["data"])


class AnthropicClient:
    VERSION = "2023-06-01"

    def __init__(self, cfg, m):
        self.cfg, self.m, self.p = cfg, m, cfg["defaults"]["params"]
        self.key = env_key(cfg["providers"]["anthropic"]["api_key_env"])
        self.base = cfg["providers"]["anthropic"]["base_url"]
        self.max_out = cfg["providers"]["anthropic"].get("max_output", self.p["api_max_output"])

    def _headers(self):
        return {"x-api-key": self.key, "anthropic-version": self.VERSION}

    def call(self, messages, seed):
        body = {"model": self.m["model_id"], "max_tokens": self.max_out,
                "temperature": self.p["temperature"], "system": messages[0]["content"],
                "messages": [{"role": "user", "content": messages[1]["content"]}]}
        if self.m.get("effort"):
            body["output_config"] = {"effort": self.m["effort"]}
        if self.m.get("thinking"):
            body["thinking"] = {"type": self.m["thinking"]}
        resp = with_backoff(lambda: _post(f"{self.base}/messages", body, self._headers()))
        text = "".join(b.get("text", "") for b in resp.get("content", []) if b.get("type") == "text")
        u = resp.get("usage", {})
        pr = self.m["price_per_m"]
        cached = u.get("cache_read_input_tokens", 0) or 0
        cost = (u.get("input_tokens", 0) * pr["input"] + cached * pr["cached_input"]
                + u.get("output_tokens", 0) * pr["output"]) / 1e6
        return {"raw_response": text, "finish_reason": resp.get("stop_reason"),
                "cutoff": resp.get("stop_reason") == "max_tokens", "tokens_in": u.get("input_tokens"),
                "tokens_in_cached": cached, "tokens_out": u.get("output_tokens"),
                "tokens_reasoning": (u.get("output_tokens_details") or {}).get("thinking_tokens", 0) or 0,
                "cost_usd": round(cost, 8),
                "reasoning_effort": f"effort={self.m.get('effort')}, thinking={self.m.get('thinking') or 'adaptive'}",
                "temperature_sent": self.p["temperature"], "seed_sent": False,
                "response_model": resp.get("model"), "system_fingerprint": None}

    def list_models(self):
        return sorted(m["id"] for m in _get(f"{self.base}/models?limit=100", self._headers())["data"])


class OllamaClient:
    def __init__(self, cfg, m):
        self.cfg, self.m = cfg, m
        self.digest = check_ollama(cfg, m["model_id"])

    def call(self, messages, seed):
        res = ollama_call(self.cfg, {**self.m, "provider": "ollama"}, messages, seed)
        if res["error"]:
            raise RuntimeError(res["error"])
        cap = self.cfg["defaults"]["params"]["max_tokens"]
        return {"raw_response": res["raw_response"], "finish_reason": None,
                "cutoff": bool(res["tokens_out"] and res["tokens_out"] >= cap), "tokens_in": res["tokens_in"],
                "tokens_in_cached": 0, "tokens_out": res["tokens_out"], "tokens_reasoning": 0, "cost_usd": 0.0,
                "reasoning_effort": None, "temperature_sent": self.cfg["defaults"]["params"]["temperature"],
                "seed_sent": True, "response_model": self.m["model_id"], "system_fingerprint": self.digest}


CLIENTS = {"openai": OpenAIClient, "anthropic": AnthropicClient, "ollama": OllamaClient}


# ---------------- spend ----------------

def vendor_spent(cfg, vendor):
    ids = {m["model_id"] for m in cfg["models"].values() if m["provider"] == vendor}
    return sum(r.get("cost_usd") or 0 for p in LOGDIR.glob("*.jsonl") for r in read_jsonl(p)
               if r.get("model_id") in ids)


def worst_case_usd(cfg, m, n_in=1500):
    pr = m.get("price_per_m")
    if not pr:
        return 0.0
    max_out = cfg["providers"].get(m["provider"], {}).get("max_output", cfg["defaults"]["params"]["api_max_output"])
    return (n_in * pr["input"] + max_out * pr["output"]) / 1e6


# ---------------- run ----------------

def log_progress(msg):
    line = f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} {msg}"
    with open(PROGRESS, "a") as f:
        f.write(line + "\n")
    print(line, flush=True)


def run_id(cid, i, mk, kind):
    return f"{kind}|{cid}|{i:04d}|{mk}"


def make_record(cfg, mk, client, cond, i, funds, kind):
    m = cfg["models"][mk]
    msgs, order = prompts.build_messages(cond, i, funds)
    sd = prompts.seed(cond["condition_id"], i)
    valid = set(prompts.FAMILIES[cond["family"]]["tickers"])
    base = {"run_id": run_id(cond["condition_id"], i, mk, kind), "phase": kind, "condition_id": cond["condition_id"],
            "family": cond["family"], "context": cond["context"], "template": cond["template"],
            "system": cond["system"], "document": cond["document"], "target_role": cond["target_role"],
            "target": cond["target"], "naming": "real", "run_index": i, "model_key": mk,
            "provider": m["provider"], "model_id": m["model_id"], "model_size": m.get("size"), "seed": sd,
            "row_order": order, **LABEL}
    t0 = time.time()
    try:
        out = client.call(msgs, sd)
    except Exception as e:  # noqa: BLE001  (logged as a failed call)
        return {**base, "error": _redact(e)[:300], "cost_usd": 0.0, "latency_ms": int((time.time() - t0) * 1000),
                "timestamp": datetime.now(timezone.utc).isoformat()}
    chosen, raw, reasoning, stripped = (None, None, None, False) if out["cutoff"] else parse(out["raw_response"], valid)
    return {**base, **out, "error": "cutoff" if out["cutoff"] else None,
            "chosen_ticker": chosen, "chosen_raw": raw, "reasoning": reasoning, "fence_stripped": stripped,
            "valid_pick": chosen in valid, "hit_output_cap": out["cutoff"],
            "latency_ms": int((time.time() - t0) * 1000), "timestamp": datetime.now(timezone.utc).isoformat()}


def run_model(cfg, mk, jobs, path, kind):
    path = safe_log_path(path)
    m = cfg["models"][mk]
    vendor = m["provider"]
    client = CLIENTS[vendor](cfg, m)
    funds = prompts.render.load_funds(prompts.render.FILLED_CSV, placeholder=False)
    cap = cfg["providers"].get(vendor, {}).get("cap_usd")
    reserve = worst_case_usd(cfg, m)
    conc = cfg["providers"].get(vendor, {}).get("concurrency", 1)
    st = {"spent": vendor_spent(cfg, vendor) if cap else 0.0, "inflight": 0, "n": 0, "bad": 0, "consec": 0,
          "stop": None, "last": time.time()}

    def one(job):
        cond, i = job
        with _lock:
            if st["stop"]:
                return
            if cap is not None and st["spent"] + (st["inflight"] + 1) * reserve > cap:
                st["stop"] = f"spend cap: ${st['spent']:.4f} spent + in-flight reserve would pass ${cap:.2f}"
                return
            st["inflight"] += 1
        rec = make_record(cfg, mk, client, cond, i, funds, kind)
        with _lock:
            st["inflight"] -= 1
            st["spent"] += rec.get("cost_usd") or 0
            st["n"] += 1
            bad = bool(rec["error"]) or not rec.get("valid_pick")
            st["bad"] += int(bad)
            st["consec"] = st["consec"] + 1 if rec["error"] else 0
            with open(path, "a") as f:
                f.write(json.dumps(rec) + "\n")
            if st["consec"] >= 3:
                st["stop"] = f"3 consecutive errors; last: {rec['error']}"
            elif st["n"] >= 40 and st["bad"] / st["n"] > 0.05:
                st["stop"] = f"{st['bad']}/{st['n']} calls failed or invalid (> 5%)"
            if time.time() - st["last"] >= 15 * 60:
                log_progress(f"STATUS {kind} {mk}: {st['n']}/{len(jobs)}, failed-or-invalid {st['bad']}, "
                             f"vendor spend ${st['spent']:.4f}")
                st["last"] = time.time()

    if jobs:
        one(jobs[0])                         # first call alone (OpenAI settings probe)
    with ThreadPoolExecutor(max_workers=max(1, conc)) as ex:
        list(ex.map(one, jobs[1:]))
    msg = (f"{kind} {mk}: {st['n']} calls this run, failed-or-invalid {st['bad']}, "
           f"vendor spend so far ${st['spent']:.4f}" + (f"; AUTO-STOP: {st['stop']}" if st["stop"] else ""))
    log_progress(msg)
    return not st["stop"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default="")
    ap.add_argument("--keys", action="store_true")
    ap.add_argument("--pilot", action="store_true")
    ap.add_argument("--pilot-tag", default="pilot", help="pilot log name, e.g. pilot2 for a re-pilot")
    ap.add_argument("--runs", type=int, default=prompts.RUNS_PER_CELL,
                    help="runs per cell (Amendment v3-1: 30 for API models)")
    a = ap.parse_args()
    cfg = yaml.safe_load(open(CONFIG))
    LOGDIR.mkdir(parents=True, exist_ok=True)
    if a.keys:
        for v in ("openai", "anthropic"):
            print(f"{v}: key found: {'yes' if env_key(cfg['providers'][v]['api_key_env']) else 'no'}")
        for v, prefix in (("openai", "gpt-5.4"), ("anthropic", "claude-")):
            m = next(mm for mm in cfg["models"].values() if mm["provider"] == v)
            try:
                ids = [i for i in CLIENTS[v](cfg, m).list_models() if i.startswith(prefix)]
                print(f"{v} models ({prefix}*): {', '.join(ids)}")
            except Exception as e:  # noqa: BLE001
                print(f"{v}: model list failed: {_redact(e)[:200]}")
        return
    conds = prompts.load_conditions()
    ok = True
    for mk in [x for x in a.models.split(",") if x]:
        if a.pilot:
            path, kind = LOGDIR / f"{a.pilot_tag}_{mk}.jsonl", a.pilot_tag
            plan = [(conds[c], 0) for c in PILOT_CELLS]
        else:
            path, kind = LOGDIR / f"main_{mk}.jsonl", "main"
            plan = [(c, i) for i in range(a.runs) for c in conds.values()]
        done = {r["run_id"] for r in read_jsonl(path) if not r.get("error")} if path.exists() else set()
        jobs = [(c, i) for c, i in plan if run_id(c["condition_id"], i, mk, kind) not in done]
        log_progress(f"START {kind} {mk}: {len(jobs)} calls to run ({len(done)} already done)")
        ok = run_model(cfg, mk, jobs, path, kind) and ok
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
