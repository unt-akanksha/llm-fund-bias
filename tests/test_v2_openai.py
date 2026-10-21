"""Study 1 v2 OpenAI extension: cost arithmetic, key redaction, extension label. Token counts are made-up fixtures."""

import pytest

from v2 import run_openai as ro


def test_call_cost_uses_cached_and_reasoning_tokens():
    price = {"input": 1.0, "cached_input": 0.1, "output": 10.0}
    usage = {"prompt_tokens": 1000, "prompt_tokens_details": {"cached_tokens": 400},
             "completion_tokens": 200, "completion_tokens_details": {"reasoning_tokens": 50}}
    assert ro.call_cost(usage, price) == pytest.approx((600 * 1.0 + 400 * 0.1 + 200 * 10.0) / 1e6)


def test_redact_hides_keys():
    assert "abc123" not in ro._redact("Incorrect API key provided: sk-proj-abc123****xyz")


def test_extension_label_and_cap():
    import yaml
    cfg = yaml.safe_load(open(ro.CONFIG))
    assert ro.EXTENSION["extension"] is True and ro.EXTENSION["label"] == "extension, post-freeze" and "v2.0-frozen-design" in ro.EXTENSION["extension_note"]
    assert cfg["spend"]["cap_usd"] <= 5.0 and cfg["concurrency"] <= 3


def _fake_run(monkeypatch, tmp_path, cost_per_call):
    monkeypatch.setattr(ro, "PROGRESS", tmp_path / "progress.log")
    monkeypatch.setattr(ro, "spent", lambda cfg: 3.0)                 # pretend $3 already spent overall
    monkeypatch.setattr(ro, "worst_case_usd", lambda cfg, mk, n_in_tokens=3000: cost_per_call)  # in-flight reserve
    monkeypatch.setattr(ro, "record", lambda cfg, mk, caller, c, i, *a: {
        "run_id": f"{c['condition_id']}|{i}", "error": None, "chosen_ticker": "VTI", "cost_usd": cost_per_call})


def test_addon_run_cap_stops_this_invocation(monkeypatch, tmp_path):
    import yaml
    from v2 import render
    cfg = yaml.safe_load(open(ro.CONFIG))
    conds = {c["condition_id"]: c for c in render.load_conditions()}
    _fake_run(monkeypatch, tmp_path, 0.5)
    log = tmp_path / "log.jsonl"
    jobs = [(conds["D2__real"], i) for i in range(10)]
    with pytest.raises(ro.SpendCapReached):                          # $2 cap for this run -> stops at $2
        ro.run_jobs(cfg, "gpt-5.4", jobs, log, "ADDON", run_cap=2.0, run_base=3.0)
    assert len(log.read_text().splitlines()) == 4


def test_addon_global_cap_still_applies(monkeypatch, tmp_path):
    import yaml
    from v2 import render
    cfg = yaml.safe_load(open(ro.CONFIG))
    conds = {c["condition_id"]: c for c in render.load_conditions()}
    _fake_run(monkeypatch, tmp_path, 0.5)
    log = tmp_path / "log.jsonl"
    with pytest.raises(ro.SpendCapReached):                          # global $5: $3 + 4 x 0.5 = $5
        ro.run_jobs(cfg, "gpt-5.4", [(conds["D7__real"], i) for i in range(10)], log, "ADDON",
                    run_cap=10.0, run_base=3.0)
    assert len(log.read_text().splitlines()) == 4
