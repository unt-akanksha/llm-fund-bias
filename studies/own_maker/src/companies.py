"""Canonical company list and parser: map suggested stocks (name and/or ticker) to company ids.

Each company: id -> (tickers, name aliases). Share classes and listings of one company map to one id
(GOOG/GOOGL -> GOOGL; BABA/9988.HK -> BABA; Facebook/Meta -> META). ETFs/funds map to "ETF:<ticker>"
and are reported separately from companies. Anything unrecognized is kept as "UNKNOWN:<text>" so
the unmatched rate can be reported and the list extended.
"""

import json
import re

COMPANIES = {
    # US mega-cap tech / communication
    "AAPL": (["AAPL"], ["apple"]),
    "MSFT": (["MSFT"], ["microsoft"]),
    "GOOGL": (["GOOGL", "GOOG"], ["alphabet", "google"]),
    "AMZN": (["AMZN"], ["amazon", "amazon com"]),
    "META": (["META", "FB"], ["meta", "meta platforms", "facebook"]),
    "NVDA": (["NVDA"], ["nvidia"]),
    "TSLA": (["TSLA"], ["tesla"]),
    "NFLX": (["NFLX"], ["netflix"]),
    "AVGO": (["AVGO"], ["broadcom"]),
    "ORCL": (["ORCL"], ["oracle"]),
    "CRM": (["CRM"], ["salesforce"]),
    "ADBE": (["ADBE"], ["adobe"]),
    "AMD": (["AMD"], ["advanced micro devices", "amd"]),
    "INTC": (["INTC"], ["intel"]),
    "CSCO": (["CSCO"], ["cisco", "cisco systems"]),
    "IBM": (["IBM"], ["ibm", "international business machines"]),
    "QCOM": (["QCOM"], ["qualcomm"]),
    "TXN": (["TXN"], ["texas instruments"]),
    "PYPL": (["PYPL"], ["paypal"]),
    "SHOP": (["SHOP"], ["shopify"]),
    "UBER": (["UBER"], ["uber", "uber technologies"]),
    "PLTR": (["PLTR"], ["palantir", "palantir technologies"]),
    "SQ": (["SQ", "XYZ"], ["block", "square"]),
    "NOW": (["NOW"], ["servicenow"]),
    "SNOW": (["SNOW"], ["snowflake"]),
    "CRWD": (["CRWD"], ["crowdstrike"]),
    "ZM": (["ZM"], ["zoom", "zoom video communications"]),
    "DIS": (["DIS"], ["disney", "walt disney"]),
    "SPOT": (["SPOT"], ["spotify"]),
    "ABNB": (["ABNB"], ["airbnb"]),
    "ASML": (["ASML"], ["asml"]),
    "TSM": (["TSM", "2330.TW"], ["taiwan semiconductor", "taiwan semiconductor manufacturing", "tsmc"]),
    "SSNLF": (["SSNLF", "005930.KS"], ["samsung", "samsung electronics"]),
    "SONY": (["SONY"], ["sony"]),
    "SAP": (["SAP"], ["sap"]),
    # China / HK
    "BABA": (["BABA", "9988.HK", "9988"], ["alibaba", "alibaba group"]),
    "TCEHY": (["TCEHY", "0700.HK", "700.HK", "0700"], ["tencent"]),
    "BIDU": (["BIDU"], ["baidu"]),
    "JD": (["JD"], ["jd com", "jd"]),
    "PDD": (["PDD"], ["pdd", "pinduoduo"]),
    "NIO": (["NIO"], ["nio"]),
    "BYDDY": (["BYDDY", "1211.HK"], ["byd"]),
    # Financials
    "BRK": (["BRK.B", "BRK.A", "BRK-B", "BRK-A", "BRK"], ["berkshire hathaway", "berkshire"]),
    "JPM": (["JPM"], ["jpmorgan chase", "jpmorgan", "jp morgan", "j p morgan"]),
    "V": (["V"], ["visa"]),
    "MA": (["MA"], ["mastercard"]),
    "BAC": (["BAC"], ["bank of america"]),
    "WFC": (["WFC"], ["wells fargo"]),
    "GS": (["GS"], ["goldman sachs"]),
    "MS": (["MS"], ["morgan stanley"]),
    "AXP": (["AXP"], ["american express"]),
    "BLK": (["BLK"], ["blackrock"]),
    "SCHW": (["SCHW"], ["charles schwab", "schwab"]),
    "C": (["C"], ["citigroup", "citi"]),
    # Health care
    "JNJ": (["JNJ"], ["johnson johnson", "johnson and johnson"]),
    "UNH": (["UNH"], ["unitedhealth", "unitedhealth group", "united health"]),
    "PFE": (["PFE"], ["pfizer"]),
    "MRK": (["MRK"], ["merck"]),
    "ABBV": (["ABBV"], ["abbvie"]),
    "LLY": (["LLY"], ["eli lilly", "lilly"]),
    "ABT": (["ABT"], ["abbott", "abbott laboratories"]),
    "TMO": (["TMO"], ["thermo fisher", "thermo fisher scientific"]),
    "AMGN": (["AMGN"], ["amgen"]),
    "MRNA": (["MRNA"], ["moderna"]),
    "ISRG": (["ISRG"], ["intuitive surgical"]),
    "NVO": (["NVO"], ["novo nordisk"]),
    "CVS": (["CVS"], ["cvs", "cvs health"]),
    "WBA": (["WBA"], ["walgreens", "walgreens boots alliance"]),
    "MDT": (["MDT"], ["medtronic"]),
    # Consumer
    "PG": (["PG"], ["procter gamble", "procter and gamble", "p g"]),
    "KO": (["KO"], ["coca cola", "the coca cola", "coke"]),
    "PEP": (["PEP"], ["pepsico", "pepsi"]),
    "WMT": (["WMT"], ["walmart"]),
    "COST": (["COST"], ["costco", "costco wholesale"]),
    "HD": (["HD"], ["home depot", "the home depot"]),
    "LOW": (["LOW"], ["lowe s", "lowes"]),
    "MCD": (["MCD"], ["mcdonald s", "mcdonalds"]),
    "NKE": (["NKE"], ["nike"]),
    "SBUX": (["SBUX"], ["starbucks"]),
    "TGT": (["TGT"], ["target", "target corporation"]),
    "CL": (["CL"], ["colgate palmolive", "colgate"]),
    "KMB": (["KMB"], ["kimberly clark"]),
    "MDLZ": (["MDLZ"], ["mondelez"]),
    "PM": (["PM"], ["philip morris", "philip morris international"]),
    "MO": (["MO"], ["altria"]),
    "UL": (["UL"], ["unilever"]),
    "NSRGY": (["NSRGY"], ["nestle", "nestlé"]),
    "LVMUY": (["LVMUY"], ["lvmh"]),
    "TM": (["TM"], ["toyota", "toyota motor"]),
    # Industrials / energy / utilities / telecom / REITs
    "XOM": (["XOM"], ["exxon", "exxonmobil", "exxon mobil"]),
    "CVX": (["CVX"], ["chevron"]),
    "NEE": (["NEE"], ["nextera", "nextera energy"]),
    "DUK": (["DUK"], ["duke energy"]),
    "SO": (["SO"], ["southern company"]),
    "D": (["D"], ["dominion energy"]),
    "BA": (["BA"], ["boeing"]),
    "CAT": (["CAT"], ["caterpillar"]),
    "HON": (["HON"], ["honeywell"]),
    "JCI": (["JCI"], ["johnson controls", "johnson controls international"]),
    "MMM": (["MMM"], ["3m"]),
    "GE": (["GE"], ["general electric", "ge aerospace"]),
    "LMT": (["LMT"], ["lockheed martin"]),
    "RTX": (["RTX"], ["raytheon", "rtx"]),
    "UNP": (["UNP"], ["union pacific"]),
    "UPS": (["UPS"], ["united parcel service", "ups"]),
    "DE": (["DE"], ["deere", "john deere", "deere company"]),
    "VZ": (["VZ"], ["verizon", "verizon communications"]),
    "T": (["T"], ["at t", "at&t"]),
    "TMUS": (["TMUS"], ["t mobile", "t mobile us"]),
    "O": (["O"], ["realty income"]),
    "AMT": (["AMT"], ["american tower"]),
    "PLD": (["PLD"], ["prologis"]),
    "LIN": (["LIN"], ["linde"]),
    "ENPH": (["ENPH"], ["enphase", "enphase energy"]),
    "F": (["F"], ["ford", "ford motor"]),
    "GM": (["GM"], ["general motors"]),
}

ETF_TICKERS = {"VOO", "SPY", "IVV", "VTI", "QQQ", "VT", "VXUS", "BND", "AGG", "SCHD", "VIG", "VYM",
               "DIA", "IWM", "VGT", "XLK", "ARKK", "VNQ", "SCHB", "ITOT", "VEA", "VWO"}
ETF_WORDS = re.compile(r"\b(etf|index fund|vanguard|ishares|spdr|invesco qqq)\b", re.I)

LEGAL_WORDS = {"inc", "incorporated", "corp", "corporation", "plc", "ltd", "limited", "adr"}  # dropped anywhere
SUFFIXES = {"co", "company", "holdings", "holding", "group", "class", "a", "b", "c", "sa", "ag", "nv", "se"}


def norm_name(s):
    """'Alphabet Inc. (Google)' -> 'alphabet google'; 'Procter & Gamble Co.' -> 'procter gamble'."""
    s = [w for w in re.sub(r"[^a-z0-9]+", " ", str(s).lower().replace("&", " ")).split() if w not in LEGAL_WORDS]
    while s and s[-1] in SUFFIXES:
        s.pop()
    while s and s[0] == "the":
        s.pop(0)
    return " ".join(s)


def norm_ticker(t):
    """'NASDAQ: GOOGL' -> 'GOOGL'; 'brk.b' -> 'BRK.B'; 'HKEX:9988' -> '9988'."""
    t = str(t).strip().upper()
    t = re.sub(r"^(NASDAQ|NYSE|HKEX|HKG|SEHK|TSX|LSE|OTC|NYSEARCA)\s*[:\-]\s*", "", t)
    return t.replace("$", "").strip()


TICKER_TO_ID = {norm_ticker(t): cid for cid, (ts, _) in COMPANIES.items() for t in ts}
# longest alias first so "bank of america" wins over shorter prefixes
ALIASES = sorted(((norm_name(a), cid) for cid, (_, al) in COMPANIES.items() for a in al),
                 key=lambda x: -len(x[0]))


def match_name(name):
    """Company id whose alias equals the normalized name or starts it at a word boundary."""
    n = norm_name(name)
    if not n:
        return None
    for alias, cid in ALIASES:
        if n == alias or n.startswith(alias + " "):
            return cid
    # alias appears later as a whole word, e.g. "Facebook (Meta Platforms)" / "Google parent Alphabet"
    for alias, cid in ALIASES:
        if len(alias) >= 4 and re.search(rf"\b{re.escape(alias)}\b", n):
            return cid
    return None


def classify_entry(company, ticker):
    """One suggested stock -> canonical id, 'ETF:<T>', or 'UNKNOWN:<text>'. Name first, then ticker."""
    t = norm_ticker(ticker) if ticker else ""
    if t in ETF_TICKERS or (company and ETF_WORDS.search(str(company))):
        return f"ETF:{t or norm_name(company)}"
    cid = match_name(company) if company else None
    if cid:
        return cid
    if t in TICKER_TO_ID:
        return TICKER_TO_ID[t]
    if t.split(".")[0] in TICKER_TO_ID and "." in t:  # e.g. "META.US"
        return TICKER_TO_ID[t.split(".")[0]]
    return f"UNKNOWN:{norm_name(company) or t}"


def parse_entries(text):
    """Raw model text -> list of (company, ticker). Tries JSON first, then 'Name (TICKER)' patterns."""
    if not text:
        return []
    obj = None
    try:
        obj = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            try:
                obj = json.loads(m.group(0))
            except json.JSONDecodeError:
                obj = None
    if isinstance(obj, dict):
        items = next((v for v in obj.values() if isinstance(v, list)), [])
        out = []
        for it in items:
            if isinstance(it, dict):
                out.append((it.get("company") or it.get("name") or "", it.get("ticker") or it.get("symbol") or ""))
            elif isinstance(it, str):
                m = re.match(r"\s*(.+?)\s*\(([A-Z0-9.\-]{1,10})\)", it)
                out.append((m.group(1), m.group(2)) if m else (it, ""))
        return out
    return [(n, t) for n, t in re.findall(r"([A-Z][\w&.,' -]{1,60}?)\s*\(([A-Z0-9.\-]{1,10})\)", text)]


def companies_in(text):
    """Ordered, de-duplicated list of canonical ids (incl. ETF:/UNKNOWN:) suggested in one response."""
    seen = []
    for name, ticker in parse_entries(text):
        cid = classify_entry(name, ticker)
        if cid not in seen:
            seen.append(cid)
    return seen
