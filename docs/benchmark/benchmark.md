---
name: Benchmark
description: Run one prompt across several models, efforts or token budgets at once and compare the sculptures side by side.
endpoint: /benchmark
category: Reference
order: 3
package: dash_model_viewer
icon: mdi:chart-box-outline
lastmod: 2026-08-09
---

.. llms_copy::Benchmark

.. toc::

### Overview

[Generative 3D art](/generative-3d) answers *can it build this?* This page
answers the question you have immediately afterwards: **what do I give up by
turning the knob down?**

It sends one prompt to several settings at once and puts the sculptures next to
each other. Part counts, triangle counts and token totals rank the runs; looking
at them tells you whether the extra tokens actually bought anything — which is
not the same question, and is why every cell renders a real `<model-viewer>`
rather than a row in a table.

---

### Live demo

.. exec::docs.benchmark.benchmark
    :code: false

---

### What the three axes mean

**Model** is the biggest lever, and not in the direction you would guess. See
the measured sweep below.

**Effort** is thinking depth. It is only sent to models that accept
`output_config.effort`; varying it across a model that rejects the parameter
would run N identical calls and present them as a comparison, so the page
refuses that combination rather than producing a confident-looking result.

**Max tokens** bounds thinking **and** response text together on Opus 5, so it
is not a safety net — it is a quality dial with a cliff. Set it too low and the
JSON is truncated mid-object and the variant fails outright. When that happens
the panel says `stop=max_tokens`, because "the model did not return usable
JSON" is a misleading way to describe running out of budget.

Only one axis varies per run. Two moving variables make a comparison
unreadable, and a full grid is a combinatorial bill.

---

### A measured sweep, and what it suggests

One prompt — *"a desert observatory, sandstone and brass, dish pointed at the
sky"* — at `effort=low`, 4,000 tokens, all three models, run concurrently:

| Model | Time | Parts | **Colours** | Triangles | Out tokens | Cost |
| :-- | --: | --: | --: | --: | --: | --: |
| Haiku 4.5 | 15.7 s | 19 | **8** | 4,146 | 2,450 | $0.014 |
| Sonnet 5 | 22.6 s | 19 | 13 | 6,842 | 2,447 | $0.042 |
| Opus 5 | 30.3 s | 22 | 12 | 5,850 | 2,837 | $0.079 |

*32 s wall clock against 69 s if run one at a time. $0.135 total.*

Read that carefully, because it is not the shape people expect:

- **Haiku produced the same part count as Sonnet** at a third of the cost and
  half the latency.
- **Haiku followed the palette rule best.** The system prompt asks for *three or
  four colours reused deliberately*. Haiku used 8; Sonnet used 13; Opus used 12.
  None of them obeyed, but the cheapest model came closest — and palette
  discipline is the single thing that most decides whether the output reads as a
  sculpture rather than a test scene.
- **Opus bought 3 extra parts for 5.8× the price.**

That does not mean "always use Haiku". It means the default on
[/generative-3d](/generative-3d) — Opus 5 at `medium` — is a choice worth
re-examining against your own prompts, which is exactly what this page is for.

.. admonition::One sample is not a finding
    :icon: radix-icons:exclamation-triangle
    :color: yellow

    Everything above is a single run per cell. Model output varies between
    runs, and a three-colour difference is well inside that variance. Repeat a
    comparison before you act on it. The table is here to show what the page
    produces, not to settle the question.

---

### Why colour count is the quality metric

Part count is the obvious number and it is nearly useless: a busier sculpture is
not a better one, and 25 parts of noise scores higher than 12 parts of
composition.

Palette size is better *for this task specifically*, because the prompt makes an
explicit, checkable demand:

> Pick a deliberate palette of three or four colours and reuse them. A different
> colour per part looks like a test scene, not a sculpture.

So `distinct(baseColorFactor)` measures **instruction adherence on the one
instruction that most affects whether the result looks composed.** It is
computed from the built `.glb` rather than the model's own claims, so it cannot
be gamed by a manifest that says one thing and builds another.

It is still a proxy. The viewers are there to be looked at.

---

### Concurrency is the whole reason this is usable

A sculpt takes about 30 seconds. Four run serially is two minutes, and nobody
runs a second sweep after waiting two minutes.

```python
with concurrent.futures.ThreadPoolExecutor(max_workers=len(variants)) as pool:
    for index, result in pool.map(one, list(enumerate(variants))):
        results.append((index, result))
```

Bounded by the variant count, which `MAX_VARIANTS` already caps at 4. The status
line reports both numbers — wall time and the serial equivalent — so the saving
is visible rather than asserted.

**Four, not six.** The excalidraw benchmark this borrows from allows six.
Here each cell carries its entire `.glb` inline as a data URL, a few hundred KB
apiece, so the callback response grows with the matrix in a way a list of
drawing elements does not.

---

### Spending

This page can spend four times per click, on a public host, with no sign-in.
`tier: auth` does not cover that: with no Clerk keys configured — the default,
and what the free deployment runs — every tier except `hidden` degrades to
`public`. That degradation is correct for *reading documentation* and useless as
a spend gate, because it fails open.

So the ceiling lives in `lib/spend.py` and does not depend on identifying
anyone:

| Limit | Default | Env var |
| :-- | :-- | :-- |
| Calls per rolling window | 40 / hour | `MODEL_MAX_CALLS_PER_WINDOW`, `MODEL_WINDOW_SECONDS` |
| Cumulative estimated spend | $5.00 | `MODEL_MAX_SPEND_USD` |

Both are checked **before** the matrix runs, priced pessimistically — every
variant costed as if it used its whole output budget. The remaining allowance is
shown next to the button, so a refusal is never a surprise.

Two honest limitations:

- **It is a blast-radius limit, not an accounting system.** The dollar figures
  are local estimates from a static price table, and ignore cache-write premiums
  and any discount. The real bill comes from Anthropic.
- **The counters are process-local.** With the single gunicorn worker
  `render.yaml` runs on the free plan that is the whole deployment; add workers
  and the effective ceiling multiplies by the worker count. A shared limit needs
  Redis or a database, which is a real dependency for a docs site to carry.

---

### Source

.. source::docs/benchmark/benchmark.py
    :defaultExpanded: false
    :withExpandedButton: true
