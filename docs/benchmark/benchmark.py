"""Run one prompt across several settings at once and compare the sculptures.

/generative-3d answers "can it build this?". This page answers the question you
have immediately afterwards: **what do I give up by turning the knob down?**
— which needs the same prompt built several ways, side by side, with the cost
of each.

FOUR THINGS THAT SHAPE THE DESIGN

1. Variants run CONCURRENTLY. They are network-bound, so a four-cell matrix
   costs roughly one sculpt's wall time instead of four. A sculpt is ~30s;
   run serially, a sweep takes two minutes and nobody runs a second one.

2. The cost is shown BEFORE you press the button, not after. An estimate that
   arrives with the results is an apology rather than a decision.

3. Every cell renders its own `<model-viewer>`. The numbers rank the runs;
   only looking at them tells you whether the extra tokens bought anything.

4. MAX_VARIANTS is 4, not 6 as on the excalidraw page this borrows from. Each
   cell carries its entire `.glb` inline as a data URL — a few hundred KB —
   so the callback response grows with the matrix in a way a list of drawing
   elements does not.
"""

from __future__ import annotations

import concurrent.futures
import time
import uuid

import dash_mantine_components as dmc
from dash import Input, Output, State, callback, dcc, html, no_update

import dash_model_viewer as dmv
from lib import spend
from lib.sculptor import MAX_TOKENS, sculpt

MAX_VARIANTS = 4

EFFORT_CHOICES = spend.EFFORTS
BUDGET_CHOICES = ["2000", "4000", "8000", "16000"]

VIEWER_ATTRS = {
    "environment-image": "neutral",
    "exposure": "1.1",
    "shadow-softness": "0.7",
}


def _panel(result, viewer_id: str):
    """One cell: its settings, its numbers, and its sculpture."""
    if not result.ok:
        return dmc.GridCol(
            dmc.Paper(
                withBorder=True, p="sm",
                children=dmc.Stack(gap=4, children=[
                    dmc.Badge(result_label(result), color="red", variant="light"),
                    dmc.Text(result.reason, size="xs", c="red"),
                ]),
            ),
            span={"base": 12, "md": 6},
        )

    return dmc.GridCol(
        dmc.Paper(
            withBorder=True, p="sm",
            children=dmc.Stack(gap="xs", children=[
                dmc.Group(gap=6, children=[
                    dmc.Badge(result_label(result), variant="light"),
                    dmc.Badge(f"{result.part_count} parts", color="violet", variant="light"),
                    # The palette count is the interesting one — see the .md.
                    dmc.Badge(f"{result.palette} colours", color="grape", variant="light"),
                    dmc.Badge(f"{result.seconds:.0f}s", color="gray", variant="light"),
                    dmc.Badge(f"~${result.usd:.3f}", color="teal", variant="light"),
                ]),
                dmc.Text(
                    f"{result.output_tokens:,} out / {result.input_tokens:,} in"
                    f"  ·  {result.triangles:,} triangles"
                    f"  ·  {len(result.glb) / 1024:.0f} KB"
                    + (f"  ·  stop={result.stop_reason}"
                       if result.stop_reason not in ("end_turn", "") else "")
                    + (f"  ·  {len(result.notes)} clamped" if result.notes else ""),
                    size="xs", c="dimmed",
                ),
                dmv.ModelViewer(
                    id=viewer_id,
                    src=result.data_url,
                    alt=f"Generated sculpture: {result.manifest.get('name', 'untitled')}",
                    camera_controls=True,
                    shadow_intensity=1,
                    attributes=VIEWER_ATTRS,
                    style={"width": "100%", "height": "300px"},
                ),
            ]),
        ),
        span={"base": 12, "md": 6},
    )


def result_label(result) -> str:
    short = result.model.replace("claude-", "")
    return f"{short} · {result.effort} · {result.max_tokens:,} tok"


component = dmc.Stack(
    gap="md",
    children=[
        dmc.Alert(
            title="This page spends real API credits",
            color="yellow",
            children=(
                "Each variant is a separate paid model call. The estimate below "
                "updates as you change the matrix — check it before running. "
                "This host also enforces a rate limit and a spend ceiling "
                "(lib/spend.py)."
            ),
        ),
        dmc.Paper(withBorder=True, p="md", children=dmc.Stack(gap="sm", children=[
            dmc.SegmentedControl(
                id="bm-axis",
                data=[
                    {"value": "effort", "label": "Vary effort"},
                    {"value": "budget", "label": "Vary max tokens"},
                    {"value": "model", "label": "Vary model"},
                ],
                value="model",
                fullWidth=True,
            ),
            # Only one axis varies at a time. Two moving variables make a
            # comparison unreadable, and a full grid is a combinatorial bill.
            dmc.CheckboxGroup(
                id="bm-efforts",
                label="Effort levels to compare",
                value=["low", "high"],
                children=dmc.Group([dmc.Checkbox(label=e, value=e)
                                    for e in EFFORT_CHOICES], gap="md"),
            ),
            dmc.CheckboxGroup(
                id="bm-budgets",
                label="Max-token budgets to compare",
                value=["2000", "8000"],
                children=dmc.Group([dmc.Checkbox(label=f"{int(b):,}", value=b)
                                    for b in BUDGET_CHOICES], gap="md"),
            ),
            dmc.CheckboxGroup(
                id="bm-models",
                label="Models to compare",
                value=["claude-haiku-4-5", "claude-opus-5"],
                children=dmc.Group([dmc.Checkbox(label=m["label"], value=m["value"])
                                    for m in spend.MODELS], gap="md"),
            ),
            dmc.Grid(gutter="md", children=[
                dmc.GridCol(dmc.Select(
                    id="bm-fixed-model", label="Fixed model",
                    data=spend.MODELS, value="claude-opus-5",
                ), span={"base": 12, "sm": 4}),
                dmc.GridCol(dmc.Select(
                    id="bm-fixed-effort", label="Fixed effort",
                    data=[{"value": e, "label": e} for e in EFFORT_CHOICES],
                    value="low",
                ), span={"base": 12, "sm": 4}),
                dmc.GridCol(dmc.NumberInput(
                    id="bm-fixed-budget", label="Fixed max tokens",
                    value=MAX_TOKENS, min=1000, max=32000, step=1000,
                ), span={"base": 12, "sm": 4}),
            ]),
            dmc.Textarea(
                id="bm-prompt",
                label="Prompt",
                description="The same prompt goes to every variant — that is what makes them comparable",
                value="a desert observatory, sandstone and brass, dish pointed at the sky",
                autosize=True, minRows=2,
            ),
            dmc.Group([
                dmc.Button("Run benchmark", id="bm-run"),
                dmc.Text(id="bm-estimate", size="sm", c="dimmed"),
            ], justify="space-between"),
        ])),
        dmc.Alert(id="bm-status", title="Status", color="gray", children="Ready."),
        dmc.Text(
            "Running every variant concurrently — about as long as one sculpt.",
            id="bm-working", size="sm", c="dimmed", display="none",
        ),
        dcc.Loading(html.Div(id="bm-results"), type="dot"),
    ],
)


def _variants(axis, efforts, budgets, models, f_model, f_effort, f_budget):
    """(model, effort, max_tokens) per cell. Exactly one axis moves."""
    f_budget = int(f_budget or MAX_TOKENS)
    if axis == "effort":
        return [(f_model, e, f_budget) for e in (efforts or [])[:MAX_VARIANTS]]
    if axis == "budget":
        return [(f_model, f_effort, int(b)) for b in (budgets or [])[:MAX_VARIANTS]]
    return [(m, f_effort, f_budget) for m in (models or [])[:MAX_VARIANTS]]


@callback(
    Output("bm-estimate", "children"),
    Input("bm-axis", "value"),
    Input("bm-efforts", "value"),
    Input("bm-budgets", "value"),
    Input("bm-models", "value"),
    Input("bm-fixed-model", "value"),
    Input("bm-fixed-effort", "value"),
    Input("bm-fixed-budget", "value"),
)
def _estimate(axis, efforts, budgets, models, f_model, f_effort, f_budget):
    """Price the matrix BEFORE it runs. See the module docstring."""
    variants = _variants(axis, efforts, budgets, models, f_model, f_effort, f_budget)
    if not variants:
        return "Select at least one variant."
    total = sum(spend.estimate_usd(m, t) for m, _e, t in variants)
    left = spend.remaining()
    return (f"{len(variants)} variant{'s' if len(variants) != 1 else ''} · "
            f"up to ~${total:.2f} if every one uses its full budget · "
            f"{left.calls_left} calls / ${left.usd_left:.2f} left on this host")


@callback(
    Output("bm-results", "children"),
    Output("bm-status", "children"),
    Output("bm-status", "color"),
    Input("bm-run", "n_clicks"),
    State("bm-axis", "value"),
    State("bm-efforts", "value"),
    State("bm-budgets", "value"),
    State("bm-models", "value"),
    State("bm-fixed-model", "value"),
    State("bm-fixed-effort", "value"),
    State("bm-fixed-budget", "value"),
    State("bm-prompt", "value"),
    running=[
        (Output("bm-run", "loading"), True, False),
        (Output("bm-run", "disabled"), True, False),
        (Output("bm-working", "display"), "block", "none"),
    ],
    prevent_initial_call=True,
)
def _run(_clicks, axis, efforts, budgets, models, f_model, f_effort, f_budget, prompt):
    if not (prompt or "").strip():
        return no_update, "Write a prompt first.", "yellow"

    variants = _variants(axis, efforts, budgets, models, f_model, f_effort, f_budget)
    if not variants:
        return no_update, "Select at least one variant to compare.", "yellow"

    # Varying effort across a model that ignores the parameter would run N
    # identical calls and present them as a comparison — worse than an error,
    # because the output looks like a result.
    if axis == "effort" and f_model not in spend.EFFORT_CAPABLE:
        return (no_update,
                f"{f_model} does not accept the effort parameter, so every variant "
                "would be identical. Pick another model, or vary a different axis.",
                "red")
    # One gate for the whole matrix, priced pessimistically.
    estimate = sum(spend.estimate_usd(m, t) for m, _e, t in variants)
    verdict = spend.check(len(variants), estimate)
    if not verdict.allowed:
        return no_update, verdict.reason, "red"

    run_id = uuid.uuid4().hex[:8]
    started = time.monotonic()

    def one(item):
        index, (model, effort, budget) = item
        began = time.monotonic()
        try:
            # The per-call budget gate is already satisfied for the matrix as a
            # whole; re-checking per variant would fail the tail of a run that
            # was approved, which is worse than approving it once.
            result = sculpt(prompt.strip(), model=model, effort=effort,
                            max_tokens=budget, enforce_budget=False)
        except Exception as exc:  # one bad variant must not lose the others
            from lib.sculptor import SculptResult
            result = SculptResult(ok=False, reason=f"{type(exc).__name__}: {exc}",
                                  model=model, effort=effort, max_tokens=budget)
        if not result.seconds:
            result.seconds = time.monotonic() - began
        return index, result

    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(variants)) as pool:
        for index, result in pool.map(one, list(enumerate(variants))):
            results.append((index, result))
    results = [r for _, r in sorted(results, key=lambda x: x[0])]

    elapsed = time.monotonic() - started
    ok = [r for r in results if r.ok]
    total_cost = sum(r.usd for r in results)
    serial = sum(r.seconds for r in results)

    status = (f"{len(ok)}/{len(results)} variants in {elapsed:.0f}s "
              f"(≈{serial:.0f}s if run one at a time) · ~${total_cost:.3f} total")
    if axis == "model" and any(m not in spend.EFFORT_CAPABLE for m, _e, _t in variants):
        status += "  ·  effort not sent to models that reject it"

    grid = dmc.Grid(gutter="md", children=[
        _panel(r, f"bm-view-{run_id}-{i}") for i, r in enumerate(results)
    ])
    return grid, status, "green" if len(ok) == len(results) else "yellow"
