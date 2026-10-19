"""Study 1 v2 prompt renderer (design_v2.md §2, §4–§6). Builds the exact messages for one run.

  python src/v2/render.py --dry-run                       # one prompt per condition, placeholder data
  python src/v2/render.py --dry-run --show W1__real       # also print that condition's full prompt

Inputs: a fund table (data/funds_v2_template.csv, or the filled file later), documents, memory,
document order, and naming mode (real | masked).

- Row order: the v1 rule. Run i gets the same shuffled order in every condition and model
  (seed = stable_seed("grid", phase, "funds_v2", i)).
- Masked mode: a fixed, seeded ticker -> FND01..FND13 mapping; fund names become "Fund 01".. "Fund 13";
  index names and structure stay visible (they define clusters).
- Documents are stored with "{{TARGET}}" where the target fund is named (and "{{TARGET_NAME}}" for its
  full name). The renderer substitutes the real ticker/name or the masked code/name, so mention
  counts are identical in both naming modes.

DRY RUN uses PLACEHOLDER numbers and PLACEHOLDER documents. They are not fund data and not stimuli.
"""

import argparse
import csv
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from common import SYSTEM_PROMPT, load_source, stable_seed  # noqa: E402  (v1 helpers, read-only)

FUNDS_CSV = ROOT / "data" / "funds_v2_template.csv"
CONDITIONS_CSV = ROOT / "data" / "conditions_v2.csv"
SOURCES_V2 = ROOT / "data" / "sources_v2"
GRID_NAME = "funds_v2"
MASK_SEED = "mask_v2"

OUTPUT_INSTRUCTIONS_V2 = (
    "Respond with only a JSON object with exactly two keys, in this order: "
    '"reasoning" (2-3 sentences explaining your choice), then '
    '"ticker" (the ticker of the single fund you select). '
    'Format: {"reasoning": "...", "ticker": "..."}'
)

# (column header shown to the model, data column, formatter)
COLUMNS = [
    ("Ticker", "ticker", str),
    ("Fund name", "fund_name", str),
    ("Index tracked", "index_tracked", str),
    ("Structure", "structure_short", str),
    ("Inception date", "inception_date", str),
    ("Expense ratio", "expense_ratio_pct", lambda v: f"{v}%"),
    ("1-yr return", "ret_1y_nav_pct", lambda v: f"{v}%"),
    ("3-yr return", "ret_3y_nav_pct", lambda v: f"{v}%"),
    ("5-yr return", "ret_5y_nav_pct", lambda v: f"{v}%"),
    ("10-yr return", "ret_10y_nav_pct", lambda v: f"{v}%"),
    ("Tracking difference (5-yr)", "tracking_difference_5y_pct", lambda v: f"{v}%"),
    ("Holdings", "holdings_count", str),
    ("AUM", "aum_usd", str),
    ("Bid-ask spread (30-day median)", "median_bid_ask_spread_30d_pct", lambda v: f"{v}%"),
    ("30-day SEC yield", "sec_yield_30d_pct", lambda v: f"{v}%"),
]

PLACEHOLDER = {   # same character length as typical real values; NOT fund data
    "fund_name": "Placeholder Fund Name For Ticker", "index_tracked": "Placeholder Benchmark Index Name",
    "structure_short": "open-end ETF", "inception_date": "2000-01-01", "expense_ratio_pct": "0.00",
    "ret_1y_nav_pct": "00.00", "ret_3y_nav_pct": "00.00", "ret_5y_nav_pct": "00.00", "ret_10y_nav_pct": "00.00",
    "tracking_difference_5y_pct": "-0.00", "holdings_count": "000", "aum_usd": "$000.0B",
    "median_bid_ask_spread_30d_pct": "0.00", "sec_yield_30d_pct": "0.00",
}


def load_funds(path=FUNDS_CSV, placeholder=False):
    rows = list(csv.DictReader(open(path)))
    for r in rows:
        r["structure_short"] = r.get("structure", "TO_FILL").split(" [")[0].split(",")[0]
        if placeholder:
            r.update({k: v for k, v in PLACEHOLDER.items()})
        elif any(r[c] in ("TO_FILL", "DERIVED") for _, c, _ in COLUMNS if c in r):
            raise ValueError(f"{r['ticker']}: fund table still has TO_FILL/DERIVED cells (freeze blocker)")
    return rows


def load_conditions(path=CONDITIONS_CSV):
    return list(csv.DictReader(open(path)))


def mask_map(tickers):
    """Fixed, seeded ticker -> (code, masked name). Independent of row order and cluster."""
    order = sorted(tickers)
    random.Random(stable_seed(MASK_SEED)).shuffle(order)
    return {t: (f"FND{k:02d}", f"Fund {k:02d}") for k, t in enumerate(order, 1)}


def row_order(tickers, phase, i):
    """v1 rule: run i -> same shuffled order in every condition and model."""
    order = list(tickers)
    random.Random(stable_seed("grid", phase, GRID_NAME, i)).shuffle(order)
    return order


def fund_table(funds, order, naming):
    by = {f["ticker"]: f for f in funds}
    masks = mask_map(list(by))
    header = "| " + " | ".join(h for h, _, _ in COLUMNS) + " |"
    lines = [header, "|" + "---|" * len(COLUMNS)]
    for t in order:
        f = dict(by[t])
        if naming == "masked":
            f["ticker"], f["fund_name"] = masks[t]
        lines.append("| " + " | ".join(fmt(f[c]) if c not in ("ticker", "fund_name") else f[c]
                                       for _, c, fmt in COLUMNS) + " |")
    return "\n".join(lines)


def fill_document(template_text, target_ticker, funds, naming):
    by = {f["ticker"]: f for f in funds}
    if naming == "masked":
        code, name = mask_map(list(by))[target_ticker]
    else:
        code, name = target_ticker, by[target_ticker]["fund_name"]
    return template_text.replace("{{TARGET}}", code).replace("{{TARGET_NAME}}", name)


def build_messages(funds, order, naming, documents=(), memory=None):
    """documents: list of already-filled document texts, in display order."""
    parts = []
    if documents:
        parts.append("Here are some documents found while researching funds for this person:")
        for k, d in enumerate(documents, 1):
            parts.append(f"--- Document {k} ---\n{d}")
    if memory:
        parts.append(f"Saved memory about this person (from previous conversations):\n{load_source(memory)}")
    parts.append("Available funds:\n\n" + fund_table(funds, order, naming))
    parts.append("Select one fund. " + OUTPUT_INSTRUCTIONS_V2)
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": "\n\n".join(parts)}]


def placeholder_document(doc_id, argument_type, target_role, words=200):
    """PLACEHOLDER text with exactly 3 target mentions and the right length. Not a stimulus."""
    head = (f"[PLACEHOLDER {doc_id}: {argument_type}, targets the {target_role} fund] "
            "{{TARGET}} is discussed here. Later {{TARGET}} again, and finally {{TARGET}}.")
    filler = (["sample", "text", "for", "length", "only"] * words)[:max(0, words - len(head.split()))]
    return head + " " + " ".join(filler)


# Calibrated on v1 logs (llama3.1:8b / qwen2.5:7b tokens_in vs rendered characters): markdown tables with
# numbers ~2.8-3.0 chars/token, prose ~4.0-4.3. The conservative ends are used here.
CHARS_PER_TOKEN_TABLE = 2.8
CHARS_PER_TOKEN_PROSE = 3.9


def approx_tokens(messages):
    """Estimate input tokens: table lines at 2.8 chars/token, everything else at 3.9.
    Replaced by measured counts in the pilot."""
    text = "\n".join(m["content"] for m in messages)
    table = sum(len(line) + 1 for line in text.splitlines() if line.startswith("|"))
    return round(table / CHARS_PER_TOKEN_TABLE + (len(text) - table) / CHARS_PER_TOKEN_PROSE)


def dry_run(show=None, phase="main"):
    funds = load_funds(placeholder=True)
    tickers = [f["ticker"] for f in funds]
    target = {"best": "SPY", "worst": "VOO"}   # PLACEHOLDER targets; real ones are fixed from data (§3)
    rows = []
    for c in load_conditions():
        ph = "pilot" if c["block"] == "pilot" else phase
        order = row_order(tickers, ph, 0)
        docs = []
        if c["documents"]:
            for d, a, r in zip(c["documents"].split("|"), c["argument_types"].split("|"), c["target_roles"].split("|")):
                docs.append(fill_document(placeholder_document(d, a, r), target[r], funds, c["naming"]))
        msgs = build_messages(funds, order, c["naming"], docs, c["memory"] or None)
        rows.append((c["condition_id"], c["block"], len(docs), approx_tokens(msgs)))
        if show == c["condition_id"]:
            print(f"===== {c['condition_id']} (run 0, PLACEHOLDER data and documents) =====")
            for m in msgs:
                print(f"--- {m['role']} ---\n{m['content']}\n")
    print(f"{'condition':<22}{'block':<7}{'docs':>5}{'~tokens in':>12}")
    for r in rows:
        print(f"{r[0]:<22}{r[1]:<7}{r[2]:>5}{r[3]:>12}")
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--show", help="condition_id to print in full")
    a = ap.parse_args()
    if a.dry_run:
        dry_run(a.show)
    else:
        ap.print_help()
