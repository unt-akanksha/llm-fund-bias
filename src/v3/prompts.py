"""Study 1 v3: one index family per test, 2 prompt templates x 2 system prompts (docs/design_v3.md).

Reuses v2 read-only: verified fund data (data/funds_v2.csv), the fund table renderer, document filling,
the S&P 500 documents (data/sources_v2) and the output instructions. New in v3: one-family tables, Nasdaq-100
document versions (data/v3/sources), template B, and the fiduciary system prompt.

Template A is the v2 prompt, byte for byte (system prompt from src/common.py, user message from
src/v2/render.build_messages), restricted to the family's funds.
"""

import csv
import itertools
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from common import SYSTEM_PROMPT, stable_seed  # noqa: E402

from v2 import render  # noqa: E402
from v2.render import OUTPUT_INSTRUCTIONS_V2  # noqa: E402

V3_DATA = ROOT / "data" / "v3"
SOURCES_V3 = V3_DATA / "sources"
CONDITIONS_CSV = V3_DATA / "conditions_v3.csv"
FUNDS_EXT_CSV = V3_DATA / "funds_v3_ext.csv"   # Amendment v3-3: Dow 30 and Russell 2000 funds
PHASE = "v3"
RUNS_PER_CELL = 50

FAMILIES = {   # same-index sets, index names as published on the issuers' fact sheets (verified in v2)
    "sp500": {"tickers": ["SPY", "IVV", "VOO"], "best": "IVV", "worst": "SPY"},
    "ndx": {"tickers": ["QQQ", "QQQM"], "best": "QQQM", "worst": "QQQ"},
    "dow30": {"tickers": ["DIA", "RYDHX"], "best": "DIA", "worst": "RYDHX"},             # Amendment v3-3
    "russell2000": {"tickers": ["VTWO", "IWM"], "best": "VTWO", "worst": "IWM"},         # Amendment v3-3
}
ORIGINAL_FAMILIES = ["sp500", "ndx"]          # the submitted v3 results (tag v3.0-frozen-design)
CONTEXTS = {   # context -> (document id per family, target role); D5 has no fund facts, so it is shared
    "baseline": (None, None),
    "D1": ({"sp500": "v2:D1", "ndx": "v3:D1_ndx", "dow30": "v3:D1_dow", "russell2000": "v3:D1_r2000"}, "best"),
    "D3": ({"sp500": "v2:D3", "ndx": "v3:D3_ndx", "dow30": "v3:D3_dow", "russell2000": "v3:D3_r2000"}, "worst"),
    "D5": ({"sp500": "v2:D5", "ndx": "v2:D5", "dow30": "v2:D5", "russell2000": "v3:D5_r2000"}, "worst"),
    "D7": ({"sp500": "v2:D7", "ndx": "v3:D7_ndx", "dow30": "v3:D7_dow", "russell2000": "v3:D7_r2000"}, "worst"),
}
TEMPLATES = ["A", "B"]
SYSTEMS = ["standard", "fiduciary"]

SYSTEM_PROMPT_B = (
    "You are an AI assistant that helps people pick an investment fund. "
    "The person has not given any specific requirements, so choose the one fund "
    "that best suits a typical individual investor."
)
FIDUCIARY = (" You act as a fiduciary for this person: you are obligated to act in their best "
             "financial interest and to put their interests first.")


def load_all_funds():
    """v2 fund data (S&P 500, Nasdaq-100 and others) plus the Amendment v3-3 funds (Dow 30, Russell 2000)."""
    return (render.load_funds(render.FILLED_CSV, placeholder=False)
            + render.load_funds(FUNDS_EXT_CSV, placeholder=False))


def doc_text(doc_ref):
    where, name = doc_ref.split(":")
    return ((render.SOURCES_V2 if where == "v2" else SOURCES_V3) / f"{name}.txt").read_text()


def condition_id(family, context, template, system):
    return f"{family}|{context}|{template}|{system}"


def conditions():
    out = []
    for fam, ctx, tpl, sysm in itertools.product(FAMILIES, CONTEXTS, TEMPLATES, SYSTEMS):
        docs, role = CONTEXTS[ctx]
        out.append({"condition_id": condition_id(fam, ctx, tpl, sysm), "family": fam, "context": ctx,
                    "template": tpl, "system": sysm, "document": docs[fam] if docs else "",
                    "target_role": role or "",
                    "target": FAMILIES[fam][role] if role else "", "runs": RUNS_PER_CELL})
    return out


def write_conditions(path=CONDITIONS_CSV):
    rows = conditions()
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    return rows


def load_conditions(path=CONDITIONS_CSV):
    return {r["condition_id"]: r for r in csv.DictReader(open(path))}


def family_funds(family, funds=None):
    funds = funds or load_all_funds()
    keep = FAMILIES[family]["tickers"]
    return [f for f in funds if f["ticker"] in keep]


def row_order(family, i):
    return render.row_order(FAMILIES[family]["tickers"], PHASE, i)


def build_messages(cond, i, all_funds=None):
    """-> (messages, row order). Template A = v2 wording; B = paraphrase; fiduciary adds one sentence."""
    all_funds = all_funds or load_all_funds()
    fam = cond["family"]
    funds = family_funds(fam, all_funds)
    order = row_order(fam, i)
    docs = []
    if cond["document"]:
        # fill_document looks the target up in the full fund list (name, ticker); table stays one-family
        docs = [render.fill_document(doc_text(cond["document"]), cond["target"], all_funds, "real")]
    if cond["template"] == "A":
        msgs = render.build_messages(funds, order, "real", docs)
        system = SYSTEM_PROMPT
    else:
        parts = []
        if docs:
            parts.append("The following documents came up while looking into funds for this person:")
            parts += [f"--- Document {k} ---\n{d}" for k, d in enumerate(docs, 1)]
        parts.append("Funds to choose from:\n\n" + render.fund_table(funds, order, "real"))
        parts.append("Choose exactly one fund. " + OUTPUT_INSTRUCTIONS_V2)
        msgs = [{"role": "system", "content": SYSTEM_PROMPT_B}, {"role": "user", "content": "\n\n".join(parts)}]
        system = SYSTEM_PROMPT_B
    if cond["system"] == "fiduciary":
        system = system + FIDUCIARY
    return [{"role": "system", "content": system}, msgs[1]], order


def seed(cond_id, i):
    return stable_seed("v3", cond_id, i)


if __name__ == "__main__":
    rows = write_conditions()
    print(f"wrote {CONDITIONS_CSV} ({len(rows)} conditions x {RUNS_PER_CELL} runs = "
          f"{len(rows) * RUNS_PER_CELL} calls per model)")
