"""The OpenAI provider: discovery, pricing, and the budget gate it feeds.

Every test here runs with the transport mocked and no key in the environment.
Nothing reaches the network, and nothing needs a secret.
"""

from __future__ import annotations

import json
from unittest import mock

import pytest

from lib import openai_client, spend


@pytest.fixture(autouse=True)
def _clean_state(monkeypatch):
    """No key, no cache, between every test."""
    for var in openai_client.KEY_VARS:
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setattr(openai_client, "_discovered", None)
    monkeypatch.setattr(openai_client, "_discovery_error", "")
    yield


def _response(payload):
    """A stand-in that behaves like a real response STREAM.

    `read()` hands the body over once and then returns b"" — which is what
    urllib does and what `_read_body`'s chunked loop terminates on. A mock
    whose `read()` returns the same bytes on every call loops forever; that is
    not a hypothetical, it is what hung this suite when `_read_body` changed
    from one `read()` to a loop.
    """
    body = json.dumps(payload).encode("utf-8")
    chunks = [body, b""]

    fake = mock.MagicMock()
    fake.read.side_effect = lambda *a, **k: chunks.pop(0) if chunks else b""
    fake.__enter__ = lambda self: self
    fake.__exit__ = lambda self, *a: False
    return fake


def _models(*ids):
    return _response({"data": [{"id": i} for i in ids]})


# --------------------------------------------------------------------------
# Key handling
# --------------------------------------------------------------------------


def test_no_key_means_unavailable_and_a_sentence_that_says_so():
    assert openai_client.available() is False
    message = openai_client.status()
    assert "CHATGPT_API_KEY" in message
    assert "Anthropic path is unaffected" in message


def test_the_owners_variable_name_is_read_first(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fallback")
    monkeypatch.setenv("CHATGPT_API_KEY", "the-owners")
    assert openai_client.api_key() == "the-owners"


def test_openai_api_key_is_accepted_as_a_fallback(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fallback")
    assert openai_client.api_key() == "fallback"


def test_status_never_contains_the_key(monkeypatch):
    monkeypatch.setenv("CHATGPT_API_KEY", "sk-secret-value")
    with mock.patch("urllib.request.urlopen", return_value=_models("gpt-6-astra")):
        openai_client.warm()
        assert "sk-secret-value" not in openai_client.status()


# --------------------------------------------------------------------------
# Discovery — the list is fetched, never written down
# --------------------------------------------------------------------------


def test_discovery_returns_what_the_api_reports(monkeypatch):
    monkeypatch.setenv("CHATGPT_API_KEY", "k")
    with mock.patch("urllib.request.urlopen", return_value=_models("a", "b")):
        assert openai_client.discover_models() == ["a", "b"]


def test_discovery_is_cached(monkeypatch):
    monkeypatch.setenv("CHATGPT_API_KEY", "k")
    with mock.patch("urllib.request.urlopen", return_value=_models("a")) as opener:
        openai_client.discover_models()
        openai_client.discover_models()
        assert opener.call_count == 1, "discovery should be fetched once at boot"


def test_a_failed_discovery_degrades_and_does_not_raise(monkeypatch):
    monkeypatch.setenv("CHATGPT_API_KEY", "k")
    with mock.patch("urllib.request.urlopen", side_effect=TimeoutError("slow")):
        assert openai_client.discover_models() == []
    assert "TimeoutError" in openai_client.discovery_error()
    assert "Anthropic path is unaffected" in openai_client.status()


def test_offered_models_are_only_those_the_key_can_actually_reach(monkeypatch):
    """The point of discovery: a priced model the key cannot reach is not
    offered, because clicking it would be an error, not a purchase."""
    monkeypatch.setenv("CHATGPT_API_KEY", "k")
    with mock.patch("urllib.request.urlopen", return_value=_models("gpt-6-astra")):
        openai_client.warm()
        offered = [m["value"] for m in openai_client.offered_models()]
    assert offered == ["gpt-6-astra"]
    assert "gpt-5.6-sol" in openai_client.PRICING, "fixture assumes sol is priced"


# --------------------------------------------------------------------------
# The $0.00 hazard — the reason offered != discovered
# --------------------------------------------------------------------------


def test_an_unpriced_model_is_never_offered(monkeypatch):
    """`spend.PRICING.get(model, (0.0, 0.0))` prices an unknown model at ZERO,
    so an unpriced model would not fail the budget gate — it would pass it,
    silently, as if free. Discovery decides what exists; pricing decides what
    we are willing to meter."""
    monkeypatch.setenv("CHATGPT_API_KEY", "k")
    with mock.patch(
        "urllib.request.urlopen", return_value=_models("gpt-6-astra", "gpt-9-unpriced")
    ):
        openai_client.warm()
        offered = [m["value"] for m in openai_client.offered_models()]
    assert "gpt-9-unpriced" not in offered
    assert spend.estimate_usd("gpt-9-unpriced", 4000) == 0.0, (
        "this is the hazard the rule above exists to avoid"
    )


def test_every_offered_model_is_priced_in_the_spend_table(monkeypatch):
    """Equal, not overlapping: a model in one table and not the other is
    either an unofferable option or an unmetered spend."""
    monkeypatch.setenv("CHATGPT_API_KEY", "k")
    with mock.patch("urllib.request.urlopen", return_value=_models(*openai_client.PRICING)):
        openai_client.warm()
        for entry in openai_client.offered_models():
            assert entry["value"] in spend.PRICING, entry["value"]
            assert spend.estimate_usd(entry["value"], 1000) > 0.0


def test_spend_table_merged_both_providers():
    assert "claude-opus-5" in spend.PRICING
    assert set(openai_client.PRICING) <= set(spend.PRICING)


# --------------------------------------------------------------------------
# The call
# --------------------------------------------------------------------------


def test_complete_json_parses_content_usage_and_finish_reason(monkeypatch):
    monkeypatch.setenv("CHATGPT_API_KEY", "k")
    payload = {
        "choices": [
            {"message": {"content": '{"parts": []}'}, "finish_reason": "stop"}
        ],
        "usage": {"prompt_tokens": 11, "completion_tokens": 22},
    }
    with mock.patch("urllib.request.urlopen", return_value=_response(payload)):
        data, usage, stop = openai_client.complete_json(
            "gpt-6-astra", "sys", "draw", {"type": "object"}, 100
        )
    assert data == {"parts": []}
    assert usage == {"input_tokens": 11, "output_tokens": 22}
    assert stop == "stop"


def test_complete_json_sends_the_schema_and_the_owners_key(monkeypatch):
    monkeypatch.setenv("CHATGPT_API_KEY", "k-123")
    captured = {}

    def _capture(request, timeout=None):
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.data.decode())
        return _response(
            {"choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}]}
        )

    with mock.patch("urllib.request.urlopen", side_effect=_capture):
        openai_client.complete_json("gpt-6-astra", "s", "p", {"type": "object"}, 50)

    assert captured["auth"] == "Bearer k-123"
    assert captured["body"]["model"] == "gpt-6-astra"
    assert captured["body"]["response_format"]["type"] == "json_schema"
    assert captured["body"]["response_format"]["json_schema"]["strict"] is True


# --------------------------------------------------------------------------
# The boot-path rule
# --------------------------------------------------------------------------


def test_offered_models_never_touches_the_network(monkeypatch):
    """A page module may call this at IMPORT.

    `spend.model_options()` is evaluated while /benchmark is being imported, so
    if this fetched, a slow third party would sit on the boot path and take
    every page down with it — which it briefly did, as an IncompleteRead during
    page import, before discovery was split into warm() and the cache.
    """
    monkeypatch.setenv("CHATGPT_API_KEY", "k")
    with mock.patch("urllib.request.urlopen") as opener:
        assert openai_client.offered_models() == []
        assert openai_client.cached_models() == []
        opener.assert_not_called()


def test_model_options_makes_no_call_and_still_lists_anthropic(monkeypatch):
    """The Anthropic key is set explicitly: since the owner's 2026-09-12
    decision, `model_options()` gates those entries on it too, so a host with
    only a CHATGPT key correctly lists no Claude models."""
    monkeypatch.setenv("CHATGPT_API_KEY", "k")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-test")
    with mock.patch("urllib.request.urlopen") as opener:
        values = [m["value"] for m in spend.model_options()]
        opener.assert_not_called()
    assert "claude-opus-5" in values
