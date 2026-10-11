"""429 handling in the shared provider code (mocked; no network): Retry-After is honoured, then success."""

import providers


class FakeResp:
    def __init__(self, status, headers=None):
        self.status_code, self.headers, self.text = status, headers or {}, ""


def test_429_retry_after_then_success(monkeypatch):
    replies = [FakeResp(429, {"retry-after": "7"}), FakeResp(429), FakeResp(200)]
    sleeps = []
    monkeypatch.setattr(providers.requests, "post", lambda *a, **k: replies.pop(0))
    monkeypatch.setattr(providers.time, "sleep", sleeps.append)
    r, retries, n429, err = providers._post_with_retries("http://x", {})
    assert r.status_code == 200 and err is None and retries == 2 and n429 == 2
    assert sleeps == [7.0, 4]          # Retry-After first, then exponential backoff (2 ** 2)


def test_gives_up_after_max_retries(monkeypatch):
    monkeypatch.setattr(providers.requests, "post", lambda *a, **k: FakeResp(429))
    monkeypatch.setattr(providers.time, "sleep", lambda s: None)
    r, retries, n429, err = providers._post_with_retries("http://x", {})
    assert err.startswith("HTTP 429") and retries == providers.MAX_RETRIES and n429 == providers.MAX_RETRIES + 1
