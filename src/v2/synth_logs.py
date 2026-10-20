"""Synthetic Study 1 v2 logs with KNOWN effects, for testing src/v2/analyze.py. NOT DATA.

  python src/v2/synth_logs.py OUT.jsonl [--null]

Every cell has exactly 100 planned calls with fixed pick counts (shuffled with a fixed seed), so mean
regret per cell is known exactly. Effects mode: worst-target documents (D3, D5, D7) push picks to SPY,
D1 pushes picks to IVV, the order cells differ, the masked baseline has a different pick distribution, and
baseline__real has 2 invalid tickers (flagged outcome). --null: every cell has the baseline distribution
and no invalid tickers, so no hypothesis should be rejected.
Rows have phase "synthetic" and synthetic = true; model_key "synthetic".
"""

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from v2 import render  # noqa: E402

BASE = {"SPY": 10, "IVV": 10, "VOO": 10, "QQQ": 5, "QQQM": 5, "VTI": 30, "ITOT": 10, "BND": 5, "AGG": 5,
        "SCHZ": 5, "VXUS": 5}
BASE_WITH_INVALID = {**BASE, "VTI": 28, "VTSAX": 2}              # 2 off-table picks
WORST_DOC = {"SPY": 50, "IVV": 5, "VOO": 5, "VTI": 25, "ITOT": 5, "BND": 5, "AGG": 5}
VALID_DOC = {"IVV": 50, "VOO": 10, "VTI": 25, "ITOT": 5, "BND": 5, "AGG": 5}
MASKED = {"VTI": 10, "ITOT": 30, "SCHB": 20, "BND": 10, "AGG": 10, "VOO": 10, "VXUS": 10}
ORDERS = {"W1": {"SPY": 40, "IVV": 10, "VTI": 50}, "W2": {"SPY": 10, "IVV": 40, "VTI": 50},
          "W3": {"SPY": 25, "IVV": 25, "VTI": 50}, "W4": {"SPY": 25, "IVV": 25, "VTI": 50}}
# exact mean regret (bps) per distribution, from C: SPY 14, IVV 2, VOO 4, QQQ 23, QQQM 16, AGG -1, SCHZ 4
EXPECTED_MEAN_REGRET = {"baseline__real": 200 / 98, "D3__real": 6.1, "D1__real": 0.2, "W1__real": 4.8,
                        "W2__real": 1.2, "W3__real": 3.0, "baseline__masked": 0.2}


def distribution(cid, null):
    base, naming = cid.split("__")
    if null:
        return BASE
    if base == "baseline":
        return BASE_WITH_INVALID if naming == "real" else MASKED
    if naming == "masked":
        return MASKED
    if base in ("D3", "D5", "D7"):
        return WORST_DOC
    if base == "D1":
        return VALID_DOC
    return ORDERS.get(base, BASE)


def make(path, null=False):
    funds = render.load_funds(render.FILLED_CSV, placeholder=False)
    by = {f["ticker"]: f for f in funds}
    masks = render.mask_map(list(by))
    conds = [c for c in render.load_conditions() if c["block"] in ("core", "order")]
    with open(path, "w") as f:
        for c in conds:
            cid = c["condition_id"]
            picks = [t for t, n in distribution(cid, null).items() for _ in range(n)]
            assert len(picks) == 100, cid
            random.Random(f"synthetic|{cid}").shuffle(picks)
            for i, t in enumerate(picks):
                if c["naming"] == "masked" and t in masks:
                    shown, name = masks[t]
                else:
                    shown, name = t, by[t]["fund_name"] if t in by else "Vanguard Total Stock Market Index Fund"
                why = "its low expense ratio and small tracking difference" if c["base_condition"] == "D1" \
                    else "it is widely known and has a long track record"
                reasoning = f"I chose {name} ({shown}) because of {why}."
                f.write(json.dumps({
                    "run_id": f"synthetic|{cid}|{i:04d}|synthetic", "phase": "synthetic", "synthetic": True,
                    "condition_id": cid, "base_condition": c["base_condition"], "naming": c["naming"],
                    "run_index": i, "model_key": "synthetic", "error": None, "chosen_ticker": t,
                    "chosen_raw": shown, "reasoning": reasoning, "hit_output_cap": False,
                    "raw_response": json.dumps({"reasoning": reasoning, "ticker": shown})}) + "\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("out")
    ap.add_argument("--null", action="store_true")
    a = ap.parse_args()
    make(a.out, a.null)
