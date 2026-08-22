"""A process-level ceiling on model spend.

WHY THIS EXISTS
---------------
The generative pages are anonymous write surfaces that cost money. On a public
host with no sign-in, "click the button" is "spend the owner's credits", and
the benchmark page spends up to four times per click.

`tier: auth` does not cover it. With no Clerk keys configured — the default
here, and what the free-tier deployment runs — every tier except `hidden`
degrades to `public` (see lib/page_tiers). That degradation is right for
*reading documentation* and useless as a *spend* gate: it fails open.

So the ceiling is enforced here instead, and it does not depend on knowing who
anyone is. Two limits, both deliberately crude:

* a rolling call-count window — bounds the rate
* a cumulative estimated-dollar ledger — bounds the day

This is a **blast-radius limit, not an accounting system.** The dollar figures
are local estimates from a static price table; the real bill comes from
Anthropic. The point is that a bored visitor with a fast finger cannot run up
a large number, not that the number is exact to the cent.

PROCESS-LOCAL, AND THAT IS STATED RATHER THAN HIDDEN
----------------------------------------------------
The counters live in module state. With one gunicorn worker — which is what
`render.yaml` runs on the free plan, for memory reasons — that is the whole
deployment. Add workers and each gets its own allowance, so the effective
ceiling multiplies by the worker count. A shared limit would need Redis or the
database, which is a real dependency for a docs site to carry; the honest
version is this plus a comment saying exactly when it stops being enough.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Deque
from collections import deque

#: Calls allowed in the rolling window. A sculpt takes ~35s, so a human
#: exploring the site cannot reach this; a script can, and that is the point.
MAX_CALLS = int(os.environ.get("MODEL_MAX_CALLS_PER_WINDOW", "40"))
WINDOW_SECONDS = int(os.environ.get("MODEL_WINDOW_SECONDS", str(60 * 60)))

#: Cumulative estimated spend ceiling for the process lifetime, in dollars.
MAX_SPEND_USD = float(os.environ.get("MODEL_MAX_SPEND_USD", "5.00"))

#: USD per million tokens, (input, output). Standard rates — deliberately not
#: the Sonnet 5 introductory pricing, so the estimate errs high.
PRICING = {
    "claude-opus-5": (5.00, 25.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-haiku-4-5": (1.00, 5.00),
}

MODELS = [
    {"value": "claude-opus-5", "label": "Claude Opus 5 · $5 / $25"},
    {"value": "claude-sonnet-5", "label": "Claude Sonnet 5 · $3 / $15"},
    {"value": "claude-haiku-4-5", "label": "Claude Haiku 4.5 · $1 / $5"},
]

#: Models that accept `output_config.effort`. Varying effort on a model that
#: rejects it would run N identical calls and present them as a comparison,
#: which is worse than an error because the output looks like a result.
EFFORT_CAPABLE = frozenset({"claude-opus-5", "claude-sonnet-5"})

EFFORTS = ["low", "medium", "high", "xhigh"]

_LOCK = threading.Lock()
_CALLS: Deque[float] = deque()
_SPENT_USD = 0.0


@dataclass
class Verdict:
    allowed: bool
    reason: str = ""
    calls_left: int = 0
    usd_left: float = 0.0


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    rate_in, rate_out = PRICING.get(model, (0.0, 0.0))
    return (input_tokens * rate_in + output_tokens * rate_out) / 1_000_000


def estimate_usd(model: str, max_tokens: int, calls: int = 1) -> float:
    """Deliberately pessimistic: prices every call as if it used its whole
    output budget. Under-promising is the right bias for a number whose job is
    to stop an accident, not to be accurate."""
    _, rate_out = PRICING.get(model, (0.0, 0.0))
    return calls * max_tokens * rate_out / 1_000_000


def _prune(now: float) -> None:
    while _CALLS and now - _CALLS[0] > WINDOW_SECONDS:
        _CALLS.popleft()


def check(calls: int = 1, estimated_usd: float = 0.0) -> Verdict:
    """Would `calls` more calls be allowed? Does not consume the allowance."""
    with _LOCK:
        now = time.monotonic()
        _prune(now)
        calls_left = MAX_CALLS - len(_CALLS)
        usd_left = MAX_SPEND_USD - _SPENT_USD

        if calls > calls_left:
            return Verdict(
                False,
                f"Rate limit: {MAX_CALLS} model calls per "
                f"{WINDOW_SECONDS // 60} minutes on this host, and "
                f"{calls_left} remain. This is a shared demo — try again later, "
                f"or run it locally with your own key.",
                max(0, calls_left), max(0.0, usd_left),
            )
        if estimated_usd > usd_left:
            return Verdict(
                False,
                f"Spend ceiling: this process has an estimated "
                f"${MAX_SPEND_USD:.2f} budget and ${usd_left:.2f} is left, "
                f"but that run could cost up to ${estimated_usd:.2f}.",
                max(0, calls_left), max(0.0, usd_left),
            )
        return Verdict(True, "", calls_left, max(0.0, usd_left))


def record(model: str, input_tokens: int, output_tokens: int) -> float:
    """Consume one call's allowance and add its measured cost to the ledger."""
    global _SPENT_USD
    spent = cost_usd(model, input_tokens, output_tokens)
    with _LOCK:
        now = time.monotonic()
        _prune(now)
        _CALLS.append(now)
        _SPENT_USD += spent
    return spent


def remaining() -> Verdict:
    return check(calls=0)


def reset() -> None:
    """Tests only."""
    global _SPENT_USD
    with _LOCK:
        _CALLS.clear()
        _SPENT_USD = 0.0
