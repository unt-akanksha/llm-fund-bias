"""Study 1 v2: cost/regret/dominance, renderer, document checker, reasoning coder, conditions.

ALL NUMBERS AND FUNDS IN THIS FILE ARE MADE-UP TEST FIXTURES. They are not fund data.
"""

import csv
from pathlib import Path

import pytest

from v2 import check_docs, cost, reasoning_codes as rc, render

ROOT = Path(__file__).resolve().parents[1]


# ---------------- cost (fixtures: fictional funds "AAA", "BBB", ...) ----------------

def F(t, er, td):
    return cost.FundCost(t, er, td)


def test_net_cost_formula_and_er_redundancy():
    f = F("AAA", 0.09, -0.12)                 # ER 9 bps, lags index by 12 bps
    assert f.er_bps == pytest.approx(9) and f.residual_bps == pytest.approx(3)
    assert cost.net_cost_bps(f) == pytest.approx(12)
    assert cost.net_cost_bps(f) == pytest.approx(-f.td_bps)          # ER + R = -TD
    assert cost.net_cost_bps(F("BBB", 0.03, 0.01)) == pytest.approx(-1)   # beats its index (e.g. lending)


def test_tracking_difference_is_fund_minus_index():
    assert cost.tracking_difference_pct(10.00, 10.05) == pytest.approx(-0.05)


def test_regret_within_set_and_singleton_zero():
    s = [F("AAA", 0.03, -0.03), F("BBB", 0.09, -0.10), F("CCC", 0.03, -0.02)]
    c = {f.ticker: cost.net_cost_bps(f) for f in s}
    assert cost.regret_bps("AAA", s) == pytest.approx(c["AAA"] - min(c.values()))
    assert cost.regret_bps("CCC", s) == 0 and cost.regret_bps("BBB", s) == pytest.approx(8)
    assert cost.regret_bps("ZZZ", [F("ZZZ", 0.5, -0.6)]) == 0          # alone on its index
    with pytest.raises(KeyError):
        cost.regret_bps("QQQ", s)


def test_er_only_sensitivity_ignores_tracking_difference():
    a, b = F("AAA", 0.20, -0.50), F("BBB", 0.15, -0.15)
    assert cost.regret_bps("AAA", [a, b], cost_fn=cost.cost_er_only_bps) == pytest.approx(5)


def test_ties_within_two_bps_inclusive_after_rounding():
    assert cost.EPS_BPS == 2.0
    assert cost.is_tie(3.0, 5.0) and cost.is_tie(2.0, 4.0000000001) and not cost.is_tie(3.0, 5.01)
    assert cost.is_tie(0.1 + 0.2, 2.3)                    # float noise removed by rounding to 0.01 bp


def test_suboptimal_only_above_two_bps():
    assert not cost.is_suboptimal(2.0) and not cost.is_suboptimal(1.999999999) and cost.is_suboptimal(2.01)


def test_dominance_strict_and_ties():
    a, b = F("AAA", 0.03, -0.03), F("BBB", 0.09, -0.10)        # A: ER 3, R 0 ; B: ER 9, R 1
    assert cost.dominates(a, b) and not cost.dominates(b, a)
    c = F("CCC", 0.035, -0.04)                                  # within 2 bps of A on ER and R
    e = F("EEE", 0.03, -0.05)                                   # R exactly 2 bps worse than A: tie, no dominance
    assert not cost.dominates(a, c) and not cost.dominates(c, a)
    d = F("DDD", 0.00, -0.10)                                   # ER 3 bps better, R 10 bps worse: no dominance
    assert not cost.dominates(a, d) and not cost.dominates(d, a)
    assert not cost.dominates(a, e) and not cost.dominates(e, a)
    assert cost.dominated_funds([a, b, c, d]) == ["BBB"]


def test_best_worst_and_tie_breaks():
    s = [F("AAA", 0.03, -0.03), F("BBB", 0.09, -0.10), F("CCC", 0.05, -0.05)]
    assert cost.best_and_worst(s) == ("AAA", "BBB")
    t = [F("AAA", 0.05, -0.05), F("BBB", 0.03, -0.055), F("CCC", 0.30, -0.30)]   # best tie: lower ER
    assert cost.best_and_worst(t)[0] == "BBB"
    v = [F("BBB", 0.03, -0.03), F("AAA", 0.03, -0.035), F("CCC", 0.30, -0.30)]   # equal ER: ticker A-Z
    assert cost.best_and_worst(v)[0] == "AAA"
    w = [F("AAA", 0.30, -0.30), F("BBB", 0.25, -0.305), F("CCC", 0.01, -0.01)]   # worst tie: higher ER
    assert cost.best_and_worst(w)[1] == "AAA"
    x = [F("AAA", 0.30, -0.30), F("BBB", 0.30, -0.30), F("CCC", 0.01, -0.01)]    # equal ER: ticker Z-A
    assert cost.best_and_worst(x)[1] == "BBB"
    assert cost.best_and_worst([F("AAA", .03, -.03), F("BBB", .03, -.035)]) == (None, None)
    # exact 2-bp gap is a tie: IVV-like (ER 3, C 2) vs VOO-like (ER 3, C 4) -> tie on C and ER -> ticker A-Z
    assert cost.best_and_worst([F("YYY", .03, -.04), F("XXX", .03, -.02), F("ZZZ", .09, -.14)]) == ("XXX", "ZZZ")
    assert cost.best_and_worst([F("AAA", .03, -.03)]) == (None, None)


# ---------------- renderer ----------------

@pytest.fixture
def funds():
    return render.load_funds(placeholder=True)


def test_row_order_matches_v1_rule_and_is_stable(funds):
    t = [f["ticker"] for f in funds]
    assert render.row_order(t, "main", 3) == render.row_order(t, "main", 3)
    assert sorted(render.row_order(t, "main", 3)) == sorted(t)
    assert render.row_order(t, "main", 3) != render.row_order(t, "main", 4)


def test_mask_map_is_fixed_bijection_with_13_codes(funds):
    t = [f["ticker"] for f in funds]
    m = render.mask_map(t)
    assert m == render.mask_map(list(reversed(t)))                      # independent of input order
    assert sorted(code for code, _ in m.values()) == [f"FND{k:02d}" for k in range(1, 14)]
    assert all(name == "Fund " + code[3:] for code, name in m.values())


def test_masked_table_hides_tickers_and_names(funds):
    t = [f["ticker"] for f in funds]
    msgs = render.build_messages(funds, render.row_order(t, "main", 0), "masked")
    table = msgs[1]["content"]
    assert not any(f"| {x} |" in table for x in t)
    assert table.count("| FND") == 13 and "Placeholder Benchmark Index Name" in table
    assert "Structure" not in table and "AUM" not in table and "Expense ratio (as published)" in table


def test_document_fill_real_and_masked(funds):
    tpl = "Buy {{TARGET}} now. {{TARGET_NAME}} is great."
    assert render.fill_document(tpl, "SPY", funds, "real").startswith("Buy SPY now.")
    code, name = render.mask_map([f["ticker"] for f in funds])["SPY"]
    assert render.fill_document(tpl, "SPY", funds, "masked") == f"Buy {code} now. {name} is great."


def test_na_is_not_given_a_percent_sign():
    assert render._pct("N/A") == "N/A" and render._pct("1.50") == "1.50%"


def test_zero_tracking_difference_prints_unsigned():
    assert render._td("+0.00") == "0.00%" and render._td("-0.00") == "0.00%" and render._td("-0.14") == "-0.14%"


def test_table_has_annualized_labels_and_returns_as_of(funds):
    t = [f["ticker"] for f in funds]
    head = render.build_messages(funds, render.row_order(t, "main", 0), "real")[1]["content"]
    assert "5-yr annualized NAV return" in head and "| Returns as of |" in head


def test_unfilled_fund_table_is_a_freeze_blocker():
    with pytest.raises(ValueError, match="TO_FILL"):
        render.load_funds(placeholder=False)


def test_dry_run_covers_every_condition(capsys):
    rows = render.dry_run()
    assert len(rows) == 28
    assert all(r[3] > 500 for r in rows)
    assert {r[2] for r in rows if r[1] == "order"} == {4}


# ---------------- document checker (DUMMY documents; not stimuli) ----------------

def dummy_doc(mentions=3, words=200, extra=""):
    head = " ".join(["{{TARGET}}"] * mentions) + (" " + extra if extra else "")
    return head + " " + " ".join(["word"] * (words - len(head.split())))


def run_check(tmp_path, funds, text, target="SPY"):
    (tmp_path / "D9.txt").write_text(text)
    return check_docs.check_all(tmp_path, {"D9": target}, funds)


def test_checker_passes_clean_dummy(tmp_path, funds):
    assert run_check(tmp_path, funds, dummy_doc()) == []


@pytest.mark.parametrize("text, msg", [
    (dummy_doc(mentions=2), "named 2x"),
    (dummy_doc(mentions=4), "named 4x"),
    (dummy_doc(words=180), "180 words"),
    (dummy_doc(words=215), "215 words"),
    (dummy_doc(extra="unlike VOO"), "another fund VOO"),
    (dummy_doc(extra="SPY"), "real identity leaked"),
])
def test_checker_fails_loudly(tmp_path, funds, text, msg):
    fails = run_check(tmp_path, funds, text)
    assert fails and any(msg in f for f in fails), fails


def test_checker_counts_masked_codes_and_missing_file(tmp_path, funds):
    code, _ = render.mask_map([f["ticker"] for f in funds])["VOO"]
    fails = run_check(tmp_path, funds, dummy_doc(extra=code))
    assert any("another fund VOO" in f for f in fails)
    assert any("missing file" in f for f in check_docs.check_all(tmp_path, {"D8": "SPY"}, funds))


# ---------------- reasoning coder ----------------

def test_dictionary_codes():
    c = rc.code_reasoning("VOO has the lowest expense ratio and a tight bid-ask spread.")
    assert c["cites_expense_ratio"] and c["cites_spread_liquidity"] and c["cites_cost"]
    c = rc.code_reasoning("Analysts recommend the most popular fund with the best 10-year returns.")
    assert c["cites_authority_source"] and c["cites_brand_size_aum"] and c["cites_past_returns"]
    assert not c["cites_cost"]
    assert rc.code_reasoning("It is a unit investment trust.")["cites_structure"]
    assert rc.code_reasoning("")["cites_cost"] == 0


def test_stratified_sample_is_balanced_and_reproducible():
    rows = [{"run_id": f"{c}{i}", "condition_id": c, "reasoning_text": ""} for c in "ABCD" for i in range(60)]
    s1, s2 = rc.stratified_sample(rows), rc.stratified_sample(rows)
    assert [r["run_id"] for r in s1] == [r["run_id"] for r in s2] and len(s1) == 100
    counts = {c: sum(r["condition_id"] == c for r in s1) for c in "ABCD"}
    assert set(counts.values()) == {25}


def test_cohen_kappa_known_values():
    assert rc.cohen_kappa([1, 0, 1, 0], [1, 0, 1, 0]) == pytest.approx(1)
    # textbook 2x2 (n = 50): both yes 20, A only 5, B only 10, both no 15 -> po 0.70, pe 0.50, kappa 0.40
    a = [1] * 20 + [1] * 5 + [0] * 10 + [0] * 15
    b = [1] * 20 + [0] * 5 + [1] * 10 + [0] * 15
    assert rc.cohen_kappa(a, b) == pytest.approx(0.4)
    assert rc.cohen_kappa([1, 1, 0, 0], [1, 0, 1, 0]) == pytest.approx(0)
    assert rc.cohen_kappa([1, 1, 1, 1], [1, 1, 1, 1]) is None
    rep = rc.kappa_report([{f"auto_{c}": 1, f"human_{c}": 1} for c in rc.CODES + ["cites_cost"]] * 3)
    assert all(v[0] is None for v in rep.values())


# ---------------- conditions file ----------------

def test_conditions_v2_matches_spec():
    rows = list(csv.DictReader(open(ROOT / "data" / "conditions_v2.csv")))
    main = [r for r in rows if r["block"] != "pilot"]
    assert len(main) == 26 and sum(int(r["runs"]) for r in main) == 2600
    order = {r["base_condition"]: r["documents"] for r in rows if r["block"] == "order"}
    assert order == {"W1": "D1|D2|D5|D3", "W2": "D2|D3|D1|D5", "W3": "D3|D5|D2|D1", "W4": "D5|D1|D3|D2"}
    for docs in order.values():                  # Williams: each doc once per position, 12 distinct pairs
        assert sorted(docs.split("|")) == ["D1", "D2", "D3", "D5"]
    pos = list(zip(*[d.split("|") for d in order.values()]))
    assert all(sorted(p) == ["D1", "D2", "D3", "D5"] for p in pos)
    pairs = [(d.split("|")[i], d.split("|")[i + 1]) for d in order.values() for i in range(3)]
    assert len(set(pairs)) == 12
    roles = {r["base_condition"]: r["target_roles"] for r in rows if r["block"] == "order"}
    assert all(v.split("|").count("best") == 2 for v in roles.values())   # balanced 2 vs 2
