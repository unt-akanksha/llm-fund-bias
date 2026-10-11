from common import parse_response

IDS = {f"F{i}" for i in range(1, 9)}


def test_clean_json():
    fid, reasoning, method = parse_response('{"reasoning": "Low fee.", "fund_id": "F1"}', IDS)
    assert (fid, reasoning, method) == ("F1", "Low fee.", "json")


def test_fund_id_is_normalized():
    assert parse_response('{"reasoning": "x", "fund_id": " f3 "}', IDS)[0] == "F3"
    assert parse_response('{"reasoning": "x", "fund_id": "F7 - Grove Global"}', IDS)[0] == "F7"


def test_fallback_takes_last_json_object():
    text = 'Thinking... {"fund_id": "F2"} Actually, final answer:\n{"reasoning": "Cheapest.", "fund_id": "F1"}'
    fid, _, method = parse_response(text, IDS)
    assert fid == "F1" and method == "regex_fallback"


def test_fallback_skips_broken_trailing_block():
    text = '{"reasoning": "ok", "fund_id": "F6"} trailing {not json}'
    assert parse_response(text, IDS)[0] == "F6"


def test_invalid_or_missing_fund_id():
    assert parse_response('{"reasoning": "x", "fund_id": "F9"}', IDS)[0] is None
    assert parse_response('{"reasoning": "x"}', IDS)[2] == "no_valid_fund_id"


def test_unparseable_and_empty():
    assert parse_response("I recommend F1.", IDS) == (None, None, "unparseable")
    assert parse_response("", IDS)[2] == "empty"
    assert parse_response(None, IDS)[2] == "empty"
