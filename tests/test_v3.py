"""Study 1 v3: prompts, parsing, write guard, spend cap. Token counts and costs here are made-up fixtures."""

import json
from pathlib import Path

import pytest
import yaml

from common import SYSTEM_PROMPT
from v2 import check_docs, render
from v3 import prompts, run


def test_conditions_grid():
    rows = prompts.conditions()
    assert len(rows) == 80 and {r["family"] for r in rows} == {"sp500", "ndx", "dow30", "russell2000"}
    assert [r["family"] for r in rows[:40]] == ["sp500"] * 20 + ["ndx"] * 20     # original 40 cells first, unchanged
    assert {(r["context"], r["target"]) for r in rows if r["family"] == "ndx" and r["target"]} == {
        ("D1", "QQQM"), ("D3", "QQQ"), ("D5", "QQQ"), ("D7", "QQQ")}
    assert {(r["context"], r["target"]) for r in rows if r["family"] == "dow30" and r["target"]} == {
        ("D1", "DIA"), ("D3", "RYDHX"), ("D5", "RYDHX"), ("D7", "RYDHX")}
    assert {(r["context"], r["target"]) for r in rows if r["family"] == "russell2000" and r["target"]} == {
        ("D1", "VTWO"), ("D3", "IWM"), ("D5", "IWM"), ("D7", "IWM")}
    assert prompts.load_conditions() == {r["condition_id"]: {k: str(v) for k, v in r.items()} for r in rows}


def test_template_A_is_v2_prompt_on_family_table():
    funds = prompts.load_all_funds()
    conds = prompts.load_conditions()
    for fam in prompts.FAMILIES:
        c = conds[f"{fam}|D5|A|standard"]
        msgs, order = prompts.build_messages(c, 3, funds)
        doc = render.fill_document(prompts.doc_text(c["document"]), c["target"], funds, "real")
        ref = render.build_messages(prompts.family_funds(fam, funds), order, "real", [doc])
        assert msgs == ref and msgs[0]["content"] == SYSTEM_PROMPT
        assert set(order) == set(prompts.FAMILIES[fam]["tickers"])
        fid, _ = prompts.build_messages(conds[f"{fam}|D5|A|fiduciary"], 3, funds)
        assert fid[1] == msgs[1] and fid[0]["content"] == SYSTEM_PROMPT + prompts.FIDUCIARY


def test_template_B_same_information():
    funds = render.load_funds(render.FILLED_CSV, placeholder=False)
    c = prompts.load_conditions()["ndx|D7|B|standard"]
    msgs, order = prompts.build_messages(c, 0, funds)
    user = msgs[1]["content"]
    assert render.fund_table(prompts.family_funds("ndx", funds), order, "real") in user
    assert render.OUTPUT_INSTRUCTIONS_V2 in user and "QQQ" in user and "SPY" not in user


def test_nasdaq_documents_pass_v2_checks():
    funds = render.load_funds(render.FILLED_CSV, placeholder=False)
    for name, target in [("D1_ndx", "QQQM"), ("D3_ndx", "QQQ"), ("D7_ndx", "QQQ")]:
        tpl = (prompts.SOURCES_V3 / f"{name}.txt").read_text()
        assert check_docs.check_document(name, tpl, target, funds, "real") == []


def test_original_prompts_unchanged_by_amendment_v3_3():
    """Adding the Dow 30 / Russell 2000 funds must not change any prompt of the original 40 cells."""
    old = render.load_funds(render.FILLED_CSV, placeholder=False)
    new = prompts.load_all_funds()
    for c in prompts.load_conditions().values():
        if c["family"] in prompts.ORIGINAL_FAMILIES:
            for i in (0, 17, 49):
                assert prompts.build_messages(c, i, old) == prompts.build_messages(c, i, new)


def test_new_family_tables_and_documents():
    funds = prompts.load_all_funds()
    for fam, docs in [("dow30", ["D1_dow", "D3_dow", "D7_dow"]), ("russell2000", ["D1_r2000", "D3_r2000", "D5_r2000", "D7_r2000"])]:
        ff = prompts.family_funds(fam, funds)
        assert {f["ticker"] for f in ff} == set(prompts.FAMILIES[fam]["tickers"])
        assert len({f["index_tracked"] for f in ff}) == 1                              # same index
        for name in docs:
            role = "best" if name.startswith("D1") else "worst"
            target = prompts.FAMILIES[fam][role]
            tpl = (prompts.SOURCES_V3 / f"{name}.txt").read_text()
            for naming in ("real", "masked"):
                assert check_docs.check_document(name, tpl, target, ff, naming) == []
    tpl = (render.SOURCES_V2 / "D5.txt").read_text()                                    # dow30 reuses D5
    assert check_docs.check_document("D5", tpl, "RYDHX", prompts.family_funds("dow30", funds), "real") == []


def test_parse_strips_only_a_code_fence():
    valid = {"SPY", "IVV", "VOO"}
    assert run.parse('{"reasoning": "r", "ticker": "IVV"}', valid) == ("IVV", "IVV", "r", False)
    assert run.parse('```json\n{"reasoning": "r", "ticker": "ivv"}\n```', valid) == ("IVV", "IVV", "r", True)
    assert run.parse("I pick IVV", valid)[0] is None
    assert run.parse('{"reasoning": "r", "ticker": "VTI"}', valid)[0] == "VTI"     # off-table: invalid pick


def test_write_guard_refuses_v2_paths():
    with pytest.raises(ValueError):
        run.safe_log_path(run.ROOT / "runs" / "raw_v2" / "main_x.jsonl")
    run.safe_log_path(run.LOGDIR / "main_x.jsonl")


def test_v3_paths_do_not_touch_v2():
    for p in [run.LOGDIR, run.PROGRESS, prompts.V3_DATA, prompts.CONDITIONS_CSV, run.CONFIG]:
        assert "v2" not in Path(p).relative_to(run.ROOT).as_posix()


class FakeClient:
    def __init__(self, cfg, m):
        pass

    def call(self, messages, seed):
        return {"raw_response": '{"reasoning": "low cost", "ticker": "IVV"}', "finish_reason": "stop",
                "cutoff": False, "tokens_in": 500, "tokens_in_cached": 0, "tokens_out": 50, "tokens_reasoning": 0,
                "cost_usd": 0.5, "reasoning_effort": "none", "temperature_sent": 1.0, "seed_sent": True,
                "response_model": "fake", "system_fingerprint": None}


def test_spend_cap_stops_before_passing(tmp_path, monkeypatch):
    cfg = yaml.safe_load(open(run.CONFIG))
    cfg["providers"]["openai"]["cap_usd"] = 2.0
    monkeypatch.setattr(run, "LOGDIR", tmp_path)
    monkeypatch.setattr(run, "PROGRESS", tmp_path / "progress.log")
    monkeypatch.setitem(run.CLIENTS, "openai", FakeClient)
    monkeypatch.setattr(run, "worst_case_usd", lambda cfg, m, n_in=1500: 0.5)
    conds = prompts.load_conditions()
    jobs = [(conds["sp500|baseline|A|standard"], i) for i in range(10)]
    assert run.run_model(cfg, "gpt-5.4-nano", jobs, tmp_path / "main_gpt-5.4-nano.jsonl", "main") is False
    rows = [json.loads(line) for line in open(tmp_path / "main_gpt-5.4-nano.jsonl")]
    assert len(rows) == 4 and sum(r["cost_usd"] for r in rows) <= 2.0
    assert all(r["study"] == "v3" and r["valid_pick"] for r in rows)
