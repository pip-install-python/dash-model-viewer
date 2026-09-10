"""The OpenAI side of the sculptor: model discovery, pricing, and one call.

WHY urllib AND NOT THE `openai` SDK
-----------------------------------
`tests/test_requirements.py` exists because Pillow was imported at module
scope in `lib/` and not declared, and a docs page carving at import took all
ten pages down on the first clean deploy. Every third-party import in `lib/`
is now a declared dependency, an image layer, and a thing to keep pinned.

The two calls this module makes are a GET and a POST against a stable REST
API. That does not earn a dependency, so it uses the standard library, adds
nothing to `requirements.txt` or the Docker image, and stays trivially
mockable in tests.

WHY THE MODEL LIST IS DISCOVERED AND THE PRICES ARE NOT
-------------------------------------------------------
`GET /v1/models` is the only authority on which models a key can actually
reach, so the list is fetched from it rather than written here — a hardcoded
id that has been retired is an outage the first time someone clicks the
button. Prices are NOT in that response and are not in any API, so they are
maintained by hand below.

That asymmetry is the reason for `offered_models()`. A model is offered only
if it is BOTH discovered AND priced, because `lib.spend` prices an unknown
model at $0.00 — so an unpriced model would slip past the budget gate as if
it were free. Discovery decides what exists; pricing decides what we are
willing to meter.
"""

from __future__ import annotations

import json
import os
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

API_ROOT = "https://api.openai.com/v1"

#: The environment variable the owner named, first. `OPENAI_API_KEY` is the
#: name the wider ecosystem uses and is accepted as a fallback so a host that
#: already sets it does not need a second copy of the same secret.
KEY_VARS = ("CHATGPT_API_KEY", "OPENAI_API_KEY")

#: USD per 1M tokens, (input, output). Hand-maintained: no OpenAI endpoint
#: reports pricing. A model absent from this table is NOT offered — see the
#: module docstring.
PRICING: Dict[str, Tuple[float, float]] = {
    "gpt-6-astra": (10.0, 50.0),
    "gpt-5.6-sol": (4.0, 20.0),
    "gpt-5.6-terra": (2.0, 12.0),
    "gpt-5.6-luna": (0.2, 1.2),
}

#: Human labels. Falls back to the raw id, so a newly-priced model still works
#: before anyone writes it a label.
LABELS = {
    "gpt-6-astra": "GPT-6 Astra",
    "gpt-5.6-sol": "GPT-5.6 Sol",
    "gpt-5.6-terra": "GPT-5.6 Terra",
    "gpt-5.6-luna": "GPT-5.6 Luna",
}

#: Discovery is retried because the failure seen in practice is a transient
#: truncated read of a ~20 KB body, which succeeds on the next attempt.
DISCOVERY_ATTEMPTS = 3
DISCOVERY_BACKOFF_SECONDS = 0.4

_discovered: Optional[List[str]] = None
_discovery_error: str = ""


def api_key() -> str:
    for var in KEY_VARS:
        value = os.environ.get(var, "").strip()
        if value:
            return value
    return ""


def available() -> bool:
    return bool(api_key())


def _read_body(response) -> bytes:
    """Read a response to the end in chunks.

    A single `response.read()` on a ~20 KB body can come back short and raise
    `http.client.IncompleteRead`; it happens intermittently to this endpoint.

    A TRUNCATED BODY IS A FAILURE, NOT A RESULT. It would be easy to keep the
    partial bytes and carry on, and that is the wrong call: a half-read
    `/v1/models` parses as a SHORTER model list, and `offered_models()` would
    then quietly stop offering whatever fell off the end. A model silently
    missing from a dropdown is far worse than a page saying discovery failed,
    so the exception is allowed out and `discover_models` retries.
    """
    chunks = []
    while True:
        chunk = response.read(65536)
        if not chunk:
            break
        chunks.append(chunk)
    return b"".join(chunks)


def _get(path: str, timeout: float) -> Dict[str, Any]:
    request = urllib.request.Request(
        f"{API_ROOT}{path}",
        headers={"Authorization": f"Bearer {api_key()}"},
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(_read_body(response).decode("utf-8"))


def discover_models(timeout: float = 10.0, force: bool = False) -> List[str]:
    """Every model id this key can reach. Cached for the process lifetime.

    Called once at boot. Failure is not fatal and is not raised: the page
    degrades to "no OpenAI models" with the reason attached, because a slow or
    unreachable third party must never stop this site from serving.
    """
    global _discovered, _discovery_error
    if _discovered is not None and not force:
        return _discovered
    if not available():
        _discovered, _discovery_error = [], "no API key is set"
        return _discovered
    try:
        # Retried because the observed failure is a TRANSIENT truncated read,
        # not a refusal: the same request succeeds on the next attempt. This
        # runs once per process, so a couple of tries costs nothing and buys
        # the feature for the whole process lifetime — where giving up would
        # cost the OpenAI models until the next deploy.
        payload = None
        last: Optional[Exception] = None
        for attempt in range(DISCOVERY_ATTEMPTS):
            try:
                payload = _get("/models", timeout)
                break
            except Exception as exc:  # noqa: BLE001  (see the clause below)
                last = exc
                if attempt + 1 < DISCOVERY_ATTEMPTS:
                    time.sleep(DISCOVERY_BACKOFF_SECONDS * (attempt + 1))
        if payload is None:
            raise last if last else RuntimeError("discovery failed")
        _discovered = sorted(
            m["id"] for m in payload.get("data", []) if isinstance(m, dict) and m.get("id")
        )
        _discovery_error = ""
    except Exception as exc:  # noqa: BLE001
        # DELIBERATELY BROAD, and this is the one place it is right.
        #
        # `warm()` runs on the boot path in run.py. Anything this raises takes
        # the whole site down before it serves a page, so the only acceptable
        # behaviour is to degrade. A narrower clause already failed once here:
        # it listed URLError, TimeoutError, ValueError and KeyError, and
        # `http.client.IncompleteRead` — which is an HTTPException and none of
        # those — escaped it and propagated out of boot.
        #
        # Enumerating exception types from a third-party transport is guessing
        # at a list nobody publishes. The degraded state is well-defined (no
        # OpenAI models, with the reason on the page), so take it for anything.
        _discovered, _discovery_error = [], f"{type(exc).__name__}: {exc}"
    return _discovered


def discovery_error() -> str:
    return _discovery_error


def cached_models() -> List[str]:
    """What discovery already found. NEVER fetches.

    This is the accessor a page module may call at import. `discover_models`
    does network I/O, and a page that does network I/O while importing is how
    a slow third party takes the whole site down at boot — the exact shape of
    the Pillow outage that `tests/test_requirements.py` exists to prevent, and
    of the IncompleteRead that this separation was added to fix. `warm()` does
    the fetching, once, from run.py.
    """
    return _discovered or []


def warm(timeout: float = 10.0) -> None:
    """Fetch discovery once at boot. Never raises; failure degrades the page."""
    discover_models(timeout)


def offered_models() -> List[Dict[str, str]]:
    """Priced AND reachable, as `{"value", "label"}` for a Dash Select.

    Reads the cache only. Before `warm()` has run this is empty, which is the
    correct answer for "what can we offer right now" and not a network call.
    """
    reachable = set(cached_models())
    return [
        {
            "value": model,
            "label": f"{LABELS.get(model, model)} · ${PRICING[model][0]:g} / ${PRICING[model][1]:g}",
        }
        for model in sorted(PRICING)
        if model in reachable
    ]


def unpriced_but_reachable() -> List[str]:
    """Models the key can reach in a priced family that we cannot meter.

    Surfaced rather than hidden: this is the set we are declining to offer,
    and a silent decline looks identical to a bug.
    """
    reachable = cached_models()
    families = {model.rsplit("-", 1)[0] for model in PRICING}
    return sorted(
        m for m in reachable
        if m not in PRICING and any(m.startswith(f) for f in families)
    )


def status() -> str:
    """One sentence for the page. Never raises, never leaks the key."""
    if not available():
        return (
            "CHATGPT_API_KEY is not set on this host, so the OpenAI models are "
            "off. The Anthropic path is unaffected."
        )
    if _discovery_error:
        return f"OpenAI model discovery failed ({_discovery_error}). The Anthropic path is unaffected."
    offered = offered_models()
    if not offered:
        return "This key reaches no model this page knows how to price."
    return f"{len(offered)} OpenAI model(s) available."


def complete_json(
    model: str,
    system: str,
    prompt: str,
    schema: Dict[str, Any],
    max_tokens: int,
    timeout: float = 120.0,
    image_data_url: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, int], str]:
    """One structured-output call. Returns `(data, usage, stop_reason)`.

    With `image_data_url`, the user turn carries the image alongside the text
    and the model is asked to look at it. The data URL is passed through
    verbatim — it is what the browser produced and what this API accepts, so
    re-encoding it would only be a chance to corrupt it.

    Raises on transport or protocol failure; the caller turns that into a
    SculptResult with a reason, exactly as the Anthropic path does.
    """
    if image_data_url:
        user_content: Any = [
            {"type": "text", "text": prompt},
            {"type": "image_url", "image_url": {"url": image_data_url}},
        ]
    else:
        user_content = prompt

    body = json.dumps(
        {
            "model": model,
            "max_completion_tokens": max_tokens,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ],
            "response_format": {
                "type": "json_schema",
                "json_schema": {"name": "scene", "strict": True, "schema": schema},
            },
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{API_ROOT}/chat/completions",
        data=body,
        headers={
            "Authorization": f"Bearer {api_key()}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    choice = (payload.get("choices") or [{}])[0]
    text = (choice.get("message") or {}).get("content") or "{}"
    usage_raw = payload.get("usage") or {}
    usage = {
        "input_tokens": int(usage_raw.get("prompt_tokens") or 0),
        "output_tokens": int(usage_raw.get("completion_tokens") or 0),
    }
    return json.loads(text), usage, choice.get("finish_reason") or ""
