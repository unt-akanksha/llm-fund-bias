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
