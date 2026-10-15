"""json_validate_failed handling (gpt-oss): final outcome, full text logged, refusal rates, sensitivity."""

import json

import pandas as pd

import analyze_stage1 as A
import run_stage1 as R

JF = 'HTTP 400: {"error":{"code":"json_validate_failed","failed_generation":"I’'


def write(path, recs):
    path.write_text("".join(json.dumps(r) + "\n" for r in recs))


def test_done_ids_treats_json_failed_as_final_only_when_flagged(tmp_path):
    p = tmp_path / "log.jsonl"
    write(p, [{"run_id": "a", "error": None}, {"run_id": "b", "error": JF}, {"run_id": "c", "error": "HTTP 429"}])
    assert R.done_ids(p) == {"a"}                              # default: retry everything that failed
    assert R.done_ids(p, json_failed_final=True) == {"a", "b"}  # gpt-oss: refusal is final; 429 still retried


class FakeResp:
    def __init__(self, body):
        self._b = body

    def json(self):
        return self._b


def test_groq_extras_logs_full_failed_generation():
    text = "I’m sorry, but I can’t help with that."
    R._LAST["r"] = FakeResp({"error": {"code": "json_validate_failed", "failed_generation": text}})
    assert R.groq_extras()["failed_generation"] == text
    R._LAST["r"] = FakeResp({"choices": [{"finish_reason": "stop"}], "usage": {}})
    assert R.groq_extras() == {"finish_reason": "stop", "reasoning_tokens": None, "failed_generation": None}


def test_refusal_table_and_sensitivity_rows(tmp_path, monkeypatch):
    raw = tmp_path / "runs" / "raw"
    raw.mkdir(parents=True)
    ok = {"provider": "groq", "error": None, "raw_response": json.dumps({"stocks": [{"company": "Microsoft",
                                                                                     "ticker": "MSFT"}]})}
    recs = [{"run_id": f"main|g|p1|{i:04d}", "model_key": "g", "prompt_id": "p1", **ok} for i in range(8)]
    recs += [{"run_id": "main|g|p1|0008", "model_key": "g", "prompt_id": "p1", "error": JF},
             {"run_id": "main|g|p1|0009", "model_key": "g", "prompt_id": "p1", "error": JF},
             {"run_id": "main|g|p1|0009", "model_key": "g", "prompt_id": "p1", **ok}]   # later answered OK
    write(raw / "stage1_main_g.jsonl", recs)
    monkeypatch.setattr(A, "STUDY", tmp_path)
    df = A.load_runs("main")
    jf = A.load_json_failed("main", set(df.run_id))
    assert len(df) == 9 and jf.run_id.tolist() == ["main|g|p1|0008"] and jf.companies.iloc[0] == []
    t = A.refusal_table(df, jf)
    assert t.final_calls.iloc[0] == 10 and t.refused.iloc[0] == 1 and abs(t.refusal_rate.iloc[0] - 0.1) < 1e-12
    excl = A.mention_matrix(df)["MSFT"].mean()
    incl = A.mention_matrix(pd.concat([df, jf], ignore_index=True))["MSFT"].mean()
    assert excl == 1.0 and abs(incl - 0.9) < 1e-12
