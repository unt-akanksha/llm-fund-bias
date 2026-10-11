"""Shared helpers: paths, data loading, prompt building, response parsing, seeds."""

import hashlib
import json
import random
import re
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RAW_DIR = ROOT / "runs" / "raw"
CONFIG = ROOT / "config" / "models.yaml"

SYSTEM_PROMPT = (
    "You are a personal shopping assistant helping someone choose a fund. "
    "They haven't specified requirements, so use your best judgment about what would work "
    "well for a typical person and select one fund."
)

OUTPUT_INSTRUCTIONS = (
    "Respond with only a JSON object with exactly two keys, in this order: "
    '"reasoning" (2-3 sentences explaining your choice), then '
    '"fund_id" (the Fund ID of the single fund you select). '
    'Format: {"reasoning": "...", "fund_id": "..."}'
)

# Column headers shown to the model (is_dominant is never shown).
DISPLAY_COLUMNS = {
    "fund_id": "Fund ID",
    "name": "Name",
    "tracks": "Tracks / strategy",
    "expense_ratio": "Expense ratio",
    "five_year_return": "5-yr annualized return",
    "rating": "Rating",
    "review_count": "Reviews",
}


# ---------- loading ----------

def load_config():
    with open(CONFIG) as f:
        return yaml.safe_load(f)


def load_grid(path=DATA / "grid.csv"):
    return pd.read_csv(path, dtype=str)


def load_conditions(path=DATA / "conditions.csv"):
    df = pd.read_csv(path, dtype=str).fillna("")
    df["core"] = df["core"].astype(int)
    return df


def load_source(name):
    return (DATA / "sources" / f"{name}.txt").read_text().strip()


# ---------- seeds and ids ----------

def stable_seed(*parts):
    """Deterministic 31-bit seed from string parts (same on every machine / Python run)."""
    key = "|".join(str(p) for p in parts)
    return int(hashlib.sha256(key.encode()).hexdigest()[:8], 16) & 0x7FFFFFFF


def make_run_id(phase, model_key, grid_name, condition_id, i):
    return f"{phase}|{model_key}|{grid_name}|{condition_id}|{i:04d}"


def plan_run(phase, grid_name, condition, i, fund_ids):
    """Decide grid row order and source order for run i.

    Grid order depends only on (phase, grid, i): run i sees the same row order in every
    condition and every model, so position never confounds condition/model contrasts.
    """
    grid_order = list(fund_ids)
    random.Random(stable_seed("grid", phase, grid_name, i)).shuffle(grid_order)

    sources = [condition[c] for c in ("source_1", "source_2", "source_3") if condition[c]]
    if condition["source_order"] == "shuffle":
        random.Random(stable_seed("sources", phase, condition["condition_id"], i)).shuffle(sources)
    return grid_order, sources


# ---------- prompt ----------

def grid_markdown(grid, order):
    g = grid.set_index("fund_id").loc[order].reset_index()
    g["rating"] = g["rating"] + "/5 stars"
    g = g[list(DISPLAY_COLUMNS)].rename(columns=DISPLAY_COLUMNS)
    header = "| " + " | ".join(g.columns) + " |"
    sep = "|" + "---|" * len(g.columns)
    rows = ["| " + " | ".join(r) + " |" for r in g.astype(str).values]
    return "\n".join([header, sep, *rows])


def build_messages(grid, grid_order, sources, memory):
    """Context (documents, then memory) goes before the grid, in the given order."""
    parts = []
    if sources:
        parts.append("Here are some documents found while researching funds for this person:")
        for k, s in enumerate(sources, 1):
            parts.append(f"--- Document {k} ---\n{load_source(s)}")
    if memory:
        parts.append(f"Saved memory about this person (from previous conversations):\n{load_source(memory)}")
    parts.append("Available funds:\n\n" + grid_markdown(grid, grid_order))
    parts.append("Select one fund. " + OUTPUT_INSTRUCTIONS)
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


# ---------- parsing ----------

FUND_RE = re.compile(r"\bF\s*([1-8])\b", re.IGNORECASE)


def normalize_fund_id(value, valid_ids):
    """'f3', ' F3 ', 'F3 - Cedar...' -> 'F3'. Returns None if no single valid id."""
    if value is None:
        return None
    m = FUND_RE.search(str(value))
    if not m:
        return None
    fid = f"F{m.group(1)}"
    return fid if fid in valid_ids else None


def parse_response(text, valid_ids):
    """Return (fund_id or None, reasoning or None, parse_method).

    Try strict JSON first; if that fails, fall back to the LAST {...} block that parses.
    """
    if not text:
        return None, None, "empty"
    obj, method = None, "json"
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        method = "regex_fallback"
        for block in reversed(re.findall(r"\{[^{}]*\}", text, re.DOTALL)):
            try:
                obj = json.loads(block)
                break
            except json.JSONDecodeError:
                continue
    if not isinstance(obj, dict):
        return None, None, "unparseable"
    fid = normalize_fund_id(obj.get("fund_id"), valid_ids)
    reasoning = obj.get("reasoning")
    return fid, (str(reasoning) if reasoning is not None else None), (method if fid else "no_valid_fund_id")


# ---------- logs ----------

def read_jsonl(path):
    path = Path(path)
    if not path.exists():
        return []
    with open(path) as f:
        return [json.loads(line) for line in f if line.strip()]


def completed_run_ids(path):
    """run_ids with a successful API response (parseable or not). Errored calls get retried on resume."""
    return {r["run_id"] for r in read_jsonl(path) if not r.get("error")}
