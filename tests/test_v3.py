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
    assert len(rows) == 40 and {r["family"] for r in rows} == {"sp500", "ndx"}
    assert sum(int(r["runs"]) for r in rows) == 2000
    assert {(r["context"], r["target"]) for r in rows if r["family"] == "ndx" and r["target"]} == {
        ("D1", "QQQM"), ("D3", "QQQ"), ("D5", "QQQ"), ("D7", "QQQ")}
    assert prompts.load_conditions() == {r["condition_id"]: {k: str(v) for k, v in r.items()} for r in rows}


def test_template_A_is_v2_prompt_on_family_table():
    funds = render.load_funds(render.FILLED_CSV, placeholder=False)
    conds = prompts.load_conditions()
    for fam in prompts.FAMILIES:
        c = conds[f"{fam}|D5|A|standard"]
        msgs, order = prompts.build_messages(c, 3, funds)
        doc = render.fill_document((render.SOURCES_V2 / "D5.txt").read_text(), c["target"], funds, "real")
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
