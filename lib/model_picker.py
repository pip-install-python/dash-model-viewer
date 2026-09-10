"""A model dropdown that is filled when the page is VIEWED, not when it is
imported.

THE BUG THIS EXISTS TO FIX
--------------------------
The obvious way to offer models is `data=spend.model_options()` in the layout.
It is wrong here, and wrong invisibly: page modules are imported while Dash
registers pages, which happens BEFORE `run.py` reaches `openai_client.warm()`.
So `model_options()` is evaluated against an empty discovery cache, freezes the
Anthropic-only list into the Select, and the OpenAI models never appear no
matter how good the key is.

Measured on this host: `model_options()` returns 3 entries at page-import time
and 7 after boot completes, against a cache holding 131 discovered models. The
dropdown had the first list.

Filling it from a one-shot `dcc.Interval` moves the read to the first render,
by which time boot has finished. It also means a page refresh picks up a key
that was added after the last deploy, instead of needing a restart.

Nothing here fetches. `spend.model_options()` reads the cache `warm()` filled;
see `lib/openai_client.py` for why a page must never fetch at import.
"""

from __future__ import annotations

from typing import List, Optional

from dash import Input, Output, State, callback, dcc
import dash_mantine_components as dmc

from lib import openai_client, spend


def components(prefix: str, default: str, label: str = "Model", **select_kwargs):
    """The one-shot timer and the Select, ready to drop into a layout.

    `prefix` namespaces the ids, so several pages can each have one.
    """
    return [
        dcc.Interval(id=f"{prefix}-model-init", interval=150, max_intervals=1),
        dmc.Select(
            id=f"{prefix}-model",
            label=label,
            # Deliberately empty: the callback below fills it on first render.
            # A default list here would be the Anthropic-only list, and would
            # look correct right up until someone set an OpenAI key.
            data=[],
            value=default,
            allowDeselect=False,
            **select_kwargs,
        ),
    ]


def register(prefix: str) -> None:
    """Wire the fill callback for `prefix`. Call once, at page import."""

    @callback(
        Output(f"{prefix}-model", "data"),
        Output(f"{prefix}-model", "value"),
        Output(f"{prefix}-model-status", "children"),
        Input(f"{prefix}-model-init", "n_intervals"),
        State(f"{prefix}-model", "value"),
    )
    def _fill(_n, current):
        options = spend.model_options()
        values: List[str] = [o["value"] for o in options]
        # Keep the user's choice if it survived; otherwise fall back to the
        # first offered model rather than leaving a value the list no longer
        # contains, which renders as a blank box.
        chosen: Optional[str] = current if current in values else (
            values[0] if values else None
        )
        return options, chosen, status_line()


def status_line() -> str:
    """One sentence about the OpenAI half, always true.

    The Anthropic models are listed unconditionally because their key either
    works or the sculpt reports that it does not. The OpenAI models are only
    listed when a key reached `/v1/models`, so their ABSENCE needs explaining
    — otherwise a missing model reads as a broken page.
    """
    if not openai_client.available():
        return (
            "Claude models only — CHATGPT_API_KEY is not set on this host. "
            "Set it to add the GPT models."
        )
    error = openai_client.discovery_error()
    if error:
        return f"Claude models only — OpenAI model discovery failed ({error})."
    offered = openai_client.offered_models()
    if not offered:
        return "Claude models only — this key reaches no model this page can price."
    names = ", ".join(o["label"].split(" · ")[0] for o in offered)
    return f"Claude models, plus {names} from CHATGPT_API_KEY."
