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


def register(prefix: str, action_ids: Optional[List[str]] = None) -> None:
    """Wire the fill callback for `prefix`. Call once, at page import.

    `action_ids` are the controls that SPEND — the buttons that start a model
    call. They are disabled when this host has no provider key, because an
    enabled button that always fails is the thing a visitor reports as a bug.
    Disabling rather than hiding is deliberate: the control staying visible
    beside the explanation is what makes the page read as deliberately off
    instead of half-built.
    """
    action_ids = action_ids or []

    @callback(
        Output(f"{prefix}-model", "data"),
        Output(f"{prefix}-model", "value"),
        Output(f"{prefix}-model-status", "children"),
        Output(f"{prefix}-model", "disabled"),
        *[Output(i, "disabled", allow_duplicate=True) for i in action_ids],
        Input(f"{prefix}-model-init", "n_intervals"),
        State(f"{prefix}-model", "value"),
        prevent_initial_call=True,
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
        off = not spend.any_provider_available()
        return (options, chosen, status_line(), off, *[off] * len(action_ids))


def status_line() -> str:
    """One sentence about what is on offer, always true.

    The no-keys case comes FIRST and it is not an error state: the owner's
    decision of 2026-09-12 is that no Render service carries a provider key,
    because the sites are documentation and there is to be no production
    spend. So an empty picker is the expected production state, and the line
    beside it has to say that plainly enough that nobody files it as a bug.

    This used to open with "Claude models only — CHATGPT_API_KEY is not set",
    which was actively misleading on a host with NEITHER key: it named the
    missing one and implied the other worked.
    """
    if not spend.any_provider_available():
        return spend.NO_KEYS_MESSAGE
    if not spend.anthropic_available():
        return (
            "GPT models only — ANTHROPIC_API_KEY is not set on this host."
        )
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
