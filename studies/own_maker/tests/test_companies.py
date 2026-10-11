"""Company parsing: aliases, share classes, listings, ETFs, unknowns, malformed output."""

import json

import pytest

from companies import COMPANIES, classify_entry, companies_in, norm_name, norm_ticker


@pytest.mark.parametrize("company, ticker, expected", [
    ("Alphabet Inc.", "GOOGL", "GOOGL"),
    ("Alphabet Inc. Class C", "GOOG", "GOOGL"),
    ("Google", "", "GOOGL"),
    ("", "GOOG", "GOOGL"),
    ("Meta Platforms, Inc.", "META", "META"),
    ("Facebook", "FB", "META"),
    ("Facebook (Meta Platforms)", "", "META"),
    ("", "FB", "META"),
    ("Alibaba Group Holding Ltd", "BABA", "BABA"),
    ("Alibaba", "9988.HK", "BABA"),
    ("", "HKEX: 9988", "BABA"),
    ("Microsoft Corporation", "NASDAQ: MSFT", "MSFT"),
    ("Berkshire Hathaway Inc. Class B", "BRK.B", "BRK"),
    ("", "BRK-B", "BRK"),
    ("Johnson & Johnson", "JNJ", "JNJ"),
    ("Procter & Gamble Co.", "PG", "PG"),
    ("The Coca-Cola Company", "KO", "KO"),
    ("McDonald's Corporation", "MCD", "MCD"),
    ("JPMorgan Chase & Co.", "JPM", "JPM"),
    ("Bank of America Corp", "BAC", "BAC"),
    ("Taiwan Semiconductor Manufacturing Company", "TSM", "TSM"),
    ("Tencent Holdings", "0700.HK", "TCEHY"),
    ("Amazon.com, Inc.", "AMZN", "AMZN"),
])
def test_aliases_map_to_one_company(company, ticker, expected):
    assert classify_entry(company, ticker) == expected


def test_name_wins_over_wrong_ticker():
    assert classify_entry("Apple Inc.", "APPL") == "AAPL"   # common ticker typo


def test_etfs_are_separate():
    assert classify_entry("Vanguard S&P 500 ETF", "VOO") == "ETF:VOO"
    assert classify_entry("SPDR S&P 500 ETF Trust", "SPY") == "ETF:SPY"


def test_unknown_is_kept():
    assert classify_entry("Zyx Robotics", "ZYXR").startswith("UNKNOWN:")


def test_normalizers():
    assert norm_name("Alphabet Inc. (Google)") == "alphabet google"
    assert norm_ticker(" nyse: brk.b ") == "BRK.B"


def test_companies_in_json_dedupes_share_classes():
    text = json.dumps({"stocks": [
        {"company": "Alphabet", "ticker": "GOOGL", "reason": "."},
        {"company": "Alphabet Class C", "ticker": "GOOG", "reason": "."},
        {"company": "Meta Platforms", "ticker": "META", "reason": "."},
        {"company": "Vanguard Total Stock Market ETF", "ticker": "VTI", "reason": "."},
        {"company": "Alibaba", "ticker": "BABA", "reason": "."},
    ]})
    assert companies_in(text) == ["GOOGL", "META", "ETF:VTI", "BABA"]


def test_companies_in_text_fallback():
    text = "Here you go: Apple (AAPL), Microsoft (MSFT) and Meta Platforms (META)."
    assert companies_in(text) == ["AAPL", "MSFT", "META"]


def test_companies_in_handles_empty_and_garbage():
    assert companies_in("") == []
    assert companies_in("I can't give financial advice.") == []


def test_no_ticker_collisions():
    seen = {}
    for cid, (tickers, _) in COMPANIES.items():
        for t in tickers:
            assert t not in seen, f"{t} used by {seen.get(t)} and {cid}"
            seen[t] = cid
