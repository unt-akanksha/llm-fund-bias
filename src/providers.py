"""One call_model() interface over Ollama (local) and Groq (hosted, free tier)."""

import os
import sys
import time
from collections import deque

import requests

MAX_RETRIES = 5
TIMEOUT_S = 180


def ollama_native_url(cfg):
    """Ollama base URL without the /v1 suffix (we use the native /api endpoints)."""
    url = os.environ.get("OLLAMA_BASE_URL") or cfg["providers"]["ollama"]["base_url"]
    return url.rstrip("/").removesuffix("/v1")


# ---------- startup checks ----------

def check_ollama(cfg, model_id):
    """Exit with a helpful message if Ollama isn't running or the model isn't pulled. Returns the digest."""
    base = ollama_native_url(cfg)
    try:
        requests.get(f"{base}/api/version", timeout=5).raise_for_status()
    except requests.RequestException:
        sys.exit(f"Ollama is not reachable at {base}. Start it with:  ollama serve")
    tags = requests.get(f"{base}/api/tags", timeout=10).json().get("models", [])
    for m in tags:
        if m["name"] == model_id or m["name"] == f"{model_id}:latest":
            return m["digest"]
    sys.exit(f"Model '{model_id}' is not pulled. Run:  ollama pull {model_id}")


def check_groq(cfg, model_cfg):
    """Verify the API key, the model id against the live /models list, and that limits are filled in."""
    key = os.environ.get(cfg["providers"]["groq"]["api_key_env"])
    if not key:
        sys.exit("GROQ_API_KEY is not set (put it in .env).")
    missing = [k for k, v in model_cfg.get("limits", {}).items() if v is None]
    if missing:
        sys.exit(f"Fill in Groq limits in config/models.yaml first: {missing}")
    r = requests.get(f"{cfg['providers']['groq']['base_url']}/models",
                     headers={"Authorization": f"Bearer {key}"}, timeout=15)
    r.raise_for_status()
    ids = {m["id"] for m in r.json()["data"]}
    if model_cfg["model_id"] not in ids:
        sys.exit(f"Groq model '{model_cfg['model_id']}' not in live /models list. Available: {sorted(ids)}")
    return None  # Groq exposes no weight digest; model_id is the version we record


# ---------- Groq per-minute throttle ----------

class MinuteThrottle:
    """Keeps requests and (estimated) tokens within per-minute limits using a rolling 60 s window."""

    def __init__(self, rpm, tpm):
        self.rpm, self.tpm = rpm, tpm
        self.events = deque()  # (timestamp, tokens)

    def wait(self, est_tokens):
        while True:
            now = time.time()
            while self.events and now - self.events[0][0] > 60:
                self.events.popleft()
            used = sum(t for _, t in self.events)
            if len(self.events) < self.rpm and used + est_tokens <= self.tpm:
                return
            time.sleep(1)

    def record(self, tokens):
        self.events.append((time.time(), tokens))


# ---------- the call ----------

def _post_with_retries(url, payload, headers=None):
    """POST with exponential backoff; honours Retry-After on 429. Returns (response|None, retries, n429, error)."""
    retries = n429 = 0
    last_err = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=TIMEOUT_S)
            if r.status_code == 200:
                return r, retries, n429, None
            last_err = f"HTTP {r.status_code}: {r.text[:200]}"
            if r.status_code == 429:
                n429 += 1
                wait = float(r.headers.get("retry-after", 2 ** (attempt + 1)))
            elif r.status_code >= 500:
                wait = 2 ** (attempt + 1)
            else:
                return r, retries, n429, last_err  # 4xx other than 429: don't retry
        except requests.RequestException as e:
            last_err, wait, r = f"{type(e).__name__}: {e}", 2 ** (attempt + 1), None
        if attempt < MAX_RETRIES:
            retries += 1
            time.sleep(min(wait, 120))
    return r, retries, n429, last_err


def call_model(cfg, model_cfg, messages, seed):
    """Send one chat request. Returns a dict of the fields we log."""
    p = {**cfg["defaults"]["params"], **model_cfg.get("params", {})}
    t0 = time.time()

    if model_cfg["provider"] == "ollama":
        payload = {
            "model": model_cfg["model_id"],
            "messages": messages,
            "format": "json",
            "stream": False,
            "options": {"temperature": p["temperature"], "num_predict": p["max_tokens"],
                        "seed": seed, "num_ctx": p.get("num_ctx", 4096)},
        }
        r, retries, n429, err = _post_with_retries(f"{ollama_native_url(cfg)}/api/chat", payload)
        body = r.json() if (r is not None and not err) else {}
        text = body.get("message", {}).get("content")
        tin, tout = body.get("prompt_eval_count"), body.get("eval_count")

    elif model_cfg["provider"] == "groq":
        key = os.environ[cfg["providers"]["groq"]["api_key_env"]]
        payload = {
            "model": model_cfg["model_id"],
            "messages": messages,
            "temperature": p["temperature"],
            "max_tokens": p["max_tokens"],
            "seed": seed,
            "response_format": {"type": "json_object"},
        }
        if model_cfg.get("reasoning_effort"):
            payload["reasoning_effort"] = model_cfg["reasoning_effort"]
        r, retries, n429, err = _post_with_retries(
            f"{cfg['providers']['groq']['base_url']}/chat/completions", payload,
            headers={"Authorization": f"Bearer {key}"})
        body = r.json() if (r is not None and not err) else {}
        choices = body.get("choices") or [{}]
        text = choices[0].get("message", {}).get("content")
        usage = body.get("usage", {})
        tin, tout = usage.get("prompt_tokens"), usage.get("completion_tokens")

    else:
        raise ValueError(f"Unknown provider {model_cfg['provider']}")

    return {
        "raw_response": text,
        "tokens_in": tin,
        "tokens_out": tout,
        "latency_ms": int((time.time() - t0) * 1000),
        "http_status": r.status_code if r is not None else None,
        "retries": retries,
        "n429": n429,
        "error": err,
    }
