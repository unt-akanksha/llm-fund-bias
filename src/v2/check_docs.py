"""Study 1 v2 document checker (design_v2.md §4.2). FREEZE BLOCKER: exits non-zero on any failure.

  python src/v2/check_docs.py --docs data/sources_v2 --targets SPY=best,VOO=worst

For each document template (data/sources_v2/D*.txt, written with {{TARGET}} / {{TARGET_NAME}}), the
checker renders it in BOTH naming modes (real and masked) and verifies that:
  1. the target fund is named exactly 3 times (ticker, full name, masked code or masked name);
  2. no other fund is named (any other ticker, fund name, masked code or masked name);
  3. the length is 190-210 words;
  4. the target's index name appears at most once.
"""

import argparse
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from v2.render import fill_document, load_funds, mask_map  # noqa: E402

REQUIRED_MENTIONS = 3
MIN_WORDS, MAX_WORDS = 190, 210
MAX_INDEX_MENTIONS = 1


def _count(text, term):
    if not term or term in ("TO_FILL", "DERIVED"):
        return 0
    return len(re.findall(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", text))


def fund_terms(fund, masks):
    """Every string that names this fund in either naming mode (real ticker/name, masked code/name)."""
    code, mname = masks[fund["ticker"]]
    real = [fund["ticker"], fund.get("fund_name", "")]
    masked = [code, mname]
    return real + masked


def check_document(doc_id, template_text, target_ticker, funds, naming):
    """Return a list of failure strings (empty = pass) for one document in one naming mode."""
    masks = mask_map([f["ticker"] for f in funds])
    by = {f["ticker"]: f for f in funds}
    text = fill_document(template_text, target_ticker, funds, naming)
    fails = []
    # 1. exact target mentions: count each mention once, preferring full names over tickers inside them
    target_terms = sorted({t for t in fund_terms(by[target_ticker], masks) if t}, key=len, reverse=True)
    scrub, n_target = text, 0
    for term in target_terms:
        k = _count(scrub, term)
        n_target += k
        scrub = re.sub(r"(?<![A-Za-z0-9])" + re.escape(term) + r"(?![A-Za-z0-9])", " ", scrub)
    if n_target != REQUIRED_MENTIONS:
        fails.append(f"{doc_id} [{naming}]: target {target_ticker} named {n_target}x (must be {REQUIRED_MENTIONS})")
    # 2. no other fund
    for t, f in by.items():
        if t == target_ticker:
            continue
        hits = {term: _count(scrub, term) for term in fund_terms(f, masks) if term}
        hits = {k: v for k, v in hits.items() if v}
        if hits:
            fails.append(f"{doc_id} [{naming}]: names another fund {t}: {hits}")
    # 3. length
    n_words = len(text.split())
    if not MIN_WORDS <= n_words <= MAX_WORDS:
        fails.append(f"{doc_id} [{naming}]: {n_words} words (must be {MIN_WORDS}-{MAX_WORDS})")
    # 4. index mentions
    n_index = _count(text, by[target_ticker].get("index_tracked", ""))
    if n_index > MAX_INDEX_MENTIONS:
        fails.append(f"{doc_id} [{naming}]: index name appears {n_index}x (max {MAX_INDEX_MENTIONS})")
    if "{{" in text:
        fails.append(f"{doc_id} [{naming}]: unfilled placeholder left in text")
    # 5. masked mode must not leak the target's real ticker or name
    if naming == "masked":
        leaks = {t: _count(text, t) for t in (target_ticker, by[target_ticker].get("fund_name", "")) if t}
        leaks = {k: v for k, v in leaks.items() if v}
        if leaks:
            fails.append(f"{doc_id} [masked]: real identity leaked: {leaks}")
    return fails


def check_all(doc_dir, targets, funds):
    """targets: {'D1': 'SPY', ...}. Returns all failures across documents and naming modes."""
    fails = []
    for doc_id, ticker in sorted(targets.items()):
        path = Path(doc_dir) / f"{doc_id}.txt"
        if not path.exists():
            fails.append(f"{doc_id}: missing file {path}")
            continue
        for naming in ("real", "masked"):
            fails += check_document(doc_id, path.read_text(), ticker, funds, naming)
    return fails


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--docs", default=str(Path(__file__).resolve().parents[2] / "data" / "sources_v2"))
    ap.add_argument("--targets", required=True, help="D1=SPY,D2=SPY,... (document -> target ticker)")
    ap.add_argument("--funds", default=None, help="filled fund CSV (default: template; names must be filled)")
    a = ap.parse_args()
    funds = load_funds(a.funds, placeholder=False) if a.funds else load_funds(placeholder=False)
    targets = dict(kv.split("=") for kv in a.targets.split(","))
    fails = check_all(a.docs, targets, funds)
    if fails:
        print("DOCUMENT CHECK FAILED (freeze blocker):")
        for f in fails:
            print("  - " + f)
        sys.exit(1)
    print(f"Document check passed: {len(targets)} documents x 2 naming modes.")


if __name__ == "__main__":
    main()
