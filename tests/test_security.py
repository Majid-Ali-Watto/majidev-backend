from types import SimpleNamespace

from backend.core.security import _CachedGet


class CountingRequest:
    def __init__(self, status=200, cache_control="public, max-age=3600"):
        self.calls = 0
        self.response = SimpleNamespace(status=status, headers={"cache-control": cache_control}, data=b"{}")

    def __call__(self, url, method="GET", **kwargs):
        self.calls += 1
        return self.response


def test_signing_keys_are_fetched_once_while_fresh():
    request = CountingRequest()
    cached = _CachedGet(request)
    assert cached("https://keys") is cached("https://keys")
    assert request.calls == 1


def test_uncacheable_or_failed_answers_are_fetched_again():
    for request in (CountingRequest(cache_control="no-store"), CountingRequest(status=500)):
        cached = _CachedGet(request)
        cached("https://keys")
        cached("https://keys")
        assert request.calls == 2
