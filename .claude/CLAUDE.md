# dash-model-viewer

## Project Overview

Two things live in this one repo, and confusing them is the first
mistake a session makes here:

1. **The package** — `dash_model_viewer/`, a Dash component library
   wrapping Google's `<model-viewer>` web component for interactive
   3D and AR. Published to PyPI.
2. **The documentation site** — everything else (`pages/`, `docs/`,
   `lib/`, `components/`, `run.py`), a fork of
   dash-documentation-boilerplate serving `modelviewer.2plot.dev`.

The site documents the package **in this checkout**, never whatever
is on PyPI: the Dockerfile ends with `pip install --no-deps .`. So a
component change and its documentation ship in the same commit, and
a docs page can demonstrate an unreleased prop.

The 1.0.0 rebuild replaced the generated component layer with a
hook-based one: no webpack, no babel, no `package.json`. The
JavaScript that ships — the hand-authored shim and Google's vendored
UMD bundle, carried as package data — is **committed, not built**.
`.claude/ARCHITECTURE.md` is the design record for why (vendoring is
a supply-chain fix, not a convenience) and is cited from `README.md`
and `dash_model_viewer/_components.py`; keep it current.

Versions, dependencies and history are deliberately not restated
here — they go stale. Read `requirements.txt` for the stack and
`CHANGELOG.md` for what changed and when.

---

## Custom Directives

| Directive | Syntax | Purpose |
|-----------|--------|---------|
| `toc` | `.. toc::` | Generate table of contents |
| `exec` | `.. exec::module.path` | Render Python component |
| `source` | `.. source::file/path.py` | Display source code |
| `kwargs` | `.. kwargs::ComponentName` | Show component props |

`source` expansion is **fence-aware**: a `.. source::` written inside
a ```` ```markdown ```` fence is documentation and stays text. Do not
"simplify" `_expand_source_directives` in `pages/markdown.py` back
into a regex sweep.

---

## Configuration

### Customization Points

| File | Purpose |
|------|---------|
| `lib/constants.py` | App-wide constants (brand, colors, `BASE_URL` — the identity source) |
| `assets/main.css` | Custom CSS styles |
| `templates/index.html` | HTML template (meta tags, JSON-LD, SEO). Its `<noscript>` block is crawler-visible: headings there start at h2, never h1 |
| `components/appshell.py` | Theme configuration, MantineProvider settings |
| `components/navbar.py` | Navigation ordering (incl. the full-height mobile drawer) |
| `components/header.py` | Header nav; the wordmark is `visibleFrom="xs"` |
| `pages/control_board.py` | `/admin/control-board` — live per-page tier + llms.txt toggles (owner/admin-gated, fails closed) |
| `lib/page_visibility.py` | The board's override store (persists to `PAGE_VISIBILITY_FILE`; overrides beat frontmatter in `lib/access.py`) |
| `lib/auth_demos.py` | Live-demo teasers rendered inside the sign-in gate cards |
| `lib/relief.py` | Pillow-backed heightmap carving for `docs/image-to-3d` |

### This fork's own shapes

- **Fork point**: `run.py` sets `SATELLITE_APP_KEY` to `"modelviewer"`
  before any hub-facing import. `lib/satellite_reporter.py` is
  byte-identical to the template by contract, so its own fallback
  says `boilerplate` — an unset variable files this site's traffic
  under the template's hub row.
- **Two CI lanes** in `.github/workflows/ci.yml`: the `test` job is
  the SITE (fleet Python, backends), `package-matrix` is the WHEEL
  across `requires-python`. `tests/test_python_version.py` is
  job-scoped for exactly that reason — see `DIVERGENCES.md`.
- **Every runtime import must be declared**:
  `tests/test_requirements.py` exists because Pillow was not, and a
  docs page carving at import took all ten pages down on the first
  deploy. Exemptions in that file are earned by companion tests, not
  asserted.

---

## Development Notes

### Adding New Documentation Pages
1. Create folder in `docs/` (e.g., `docs/my-topic/`)
2. Create markdown file with frontmatter:
```markdown
---
name: My Topic
description: Description of my topic
endpoint: /my-topic
icon: mdi:cube-outline
lastmod: 2026-08-26
---

.. toc::

## Overview
...
```
3. Add Python examples as needed, exposing a module-level `component`
4. Reference with `.. exec::docs.my-topic.example`
5. Page auto-registers and appears in navigation

`lastmod:` is a literal, stamped from the file's real authoring date.
Never script it from mtime at build time — that is the invented-date
sitemap the dimll floor exists to end.

### Demo models
`lib/demo_models.py` holds the shared model URLs. Examples import
from there rather than hardcoding a CDN path, so one edit re-points
every page.

---

## Resources

- [Dash Documentation](https://dash.plotly.com/)
- [Dash Mantine Components](https://www.dash-mantine-components.com/)
- [`<model-viewer>`](https://modelviewer.dev/)
- [dash-improve-my-llms](https://pypi.org/project/dash-improve-my-llms/)
- [Project Repository](https://github.com/pip-install-python/dash-model-viewer)
- [Template](https://github.com/pip-install-python/Dash-Documentation-Boilerplate)

---

## Network role & the behavioral contract

This repo is a member of the 2plot network — either the template
itself (dash-documentation-boilerplate) or a fork of it serving one
component's documentation. **Identity derives from the repo, never
from this file**: the app key comes from `SATELLITE_APP_KEY` and
run.py's fork point, the host from `lib/constants.py`'s `BASE_URL`,
the deliberate differences from the template from `DIVERGENCES.md`
at the repo root. If those disagree with anything written here,
they win.

### The contract — every session, every prompt

1. **Check the prompt against this tree before executing.** Prompts
   are written from the template's perspective and your fork may
   legitimately differ — floors, backends, payload shapes, page
   sets. A prompt step that doesn't fit this repo is a finding to
   return, not an instruction to force.
2. **Corrections are your job, not scope creep.** If a prompt's
   reference list doesn't match its steps, if its assumed state is
   wrong, or if executing it as written would produce a
   green-but-vacuous result, say so and propose the corrected
   version before running it.
3. **Verify your own deploy on the wire before reporting.** A push
   is not a result. Run `/wire-verify` (or its manual equivalent)
   against production and paste what came back. If your sandbox
   cannot reach your own domain, say exactly that — an unverified
   claim marked as unverified is honest; the same claim unmarked is
   not.
4. **Report observed versus expected, with evidence.** Paste the
   JSON, the status code, the test count. "Should work" and summary
   claims without artifacts are not reports.
5. **Divergence is legitimate when written down.** Before syncing
   template changes, read `DIVERGENCES.md`; never let a sync
   "restore" a recorded deliberate difference. When you deliberately
   diverge, record it there in the same commit — an unrecorded
   divergence is indistinguishable from drift and will be treated
   as drift.
6. **Never touch**: environment variable VALUES, hosting dashboards,
   secrets, other repos' trees, or anything the prompt didn't put in
   scope. Enumerate what you cannot do (closing PRs, dashboard
   steps) for the owner instead of claiming it done.

### Verification traps (fleet-learned, keep them)

- A `>=` floor can never pull a new release through a Docker cache
  hit — the requirements line changing IS the cache bust, and floors
  live in several encodings (requirements, run.py's boot floor,
  tests, CI): grep the number, move every one.
- `/healthz` build == HEAD is the deploy proof; a missing geo block
  on dimll ≥2.7 means the cache trap fired (unless DIVERGENCES.md
  says this host's healthz is deliberately minimal).
- Probe with GET, not HEAD — HEAD responses omit the Link headers.
- Run-watchers keyed on a commit sha can match Dependabot's runs on
  the same sha — key on the workflow path (cd.yml) instead.
- The browser lane and the machine lane are different documents;
  a fix proven on one is unproven on the other.
- A bot-merged PR — any GITHUB_TOKEN merge — lands with ZERO
  workflow runs on the merge sha (anti-recursion) yet still reaches
  production: the deploy hook builds branch HEAD, so an in-flight
  CD run ships the merge while its own build-match wait holds out
  for the superseded release sha. Observed live on 4a1d430
  (2026-08-25). Since 1.6.25 the wait fails FAST on this (live
  build a descendant of the wanted sha, via the compare API)
  instead of going red at timeout, and the remedy is policy —
  actions PRs: human merge when green; never a bot actor on main.
- There is ONE classifier: `dash_improve_my_llms.classify()`. Never
  add a User-Agent list to this app — the tracker had one for a year
  (`lib/analytics_tracker.py`, until the 2.8.0 floor), it filed
  ClaudeBot as *search* (it is Anthropic's training crawler; the
  package's registry and this repo's own `run.py` comment both said
  so six lines from where the list ignored them), it still named the
  retired `anthropic-ai` / `claude-web` tokens, and it counted every
  UA-less or library client as a human. Every host in the fleet
  reported those numbers. A token the registry lacks is a pushback to
  the package seat, not a list here;
  `tests/test_analytics_classifier.py` greps the module for the old
  tokens and goes red if one comes back.
- `build == HEAD` on `/healthz` means HEAD of **`release`**, not main
  (sync item 13). Render deploys `release`; only cd.yml's `deploy`
  job writes it, fast-forward, after the CI matrix is green. `main`
  ahead of `release` is an uncertified push pending — its CD run is
  red or still running — never "drift" and never a reason to deploy
  by hand or to write `release` yourself (a non-fast-forward push
  fails the next run on purpose). Compare the wire against
  `git rev-parse origin/release`; the measurement behind this:
  2026-08-29 14:12Z on the template, de0bcff pushed to main, built by
  Render inside the minute, red in CD at 14:13Z, served for ~6
  minutes. A host whose DIVERGENCES.md posture fence has no `deploy:`
  key still watches main — there the trap is the old one.

- Which branch Render actually builds can be measured on a GREEN push,
  by TIMING, without waiting for a red one (leaflet, 2026-08-31 — the
  method, not just its answer). `main == release == wire` at every step
  of a promote tells you nothing: both refs hold the same sha, so the
  wire cannot separate them, and four promotes across three hosts said
  nothing at all. Sample `/healthz` every ~45 s from the moment of the
  push and note when the swap lands relative to the PROMOTE, not the
  push. leaflet measured build+swap at 2m03s from the promote; had
  Render reacted to the push instead, the same 2m03s would have put the
  build live ~1m52s earlier than it appeared, and the wire was still
  serving the old sha well past that point. That is STRONG EVIDENCE
  that Render is building `release` — not proof, since a queued or slow
  build could in principle produce the same shape. The canonical
  discriminator is unchanged and still owed: the first push that goes
  RED on main must leave `release` unmoved and the wire unchanged.
  Worth taking on every SECOND promote — it costs one background
  sampler and converts "asserted" into "strongly evidenced".
- Verify the artifact the claim is about, and say which one you
  measured. Three hosts got this wrong in one round while holding the
  rule: a skip link checked in the received HTML lives in the RENDERED
  DOM (muicharts, twice inside an hour, having written the rule
  itself); a props table absent from the crawler document is a defect
  of the site, not of the harness — pannellum moved that assertion onto
  the rendered layout and the pin passed for a fortnight over a corpus
  serving zero props. WHEN A LANE DISAGREES, THAT IS THE FINDING; never
  relocate the assertion to the lane that passes. And an owner-gated
  section needs BOTH cookie states to be a measurement at all (this
  host, 2026-08-31: `credentials: 'include'` → 2,962 B with admin
  hrefs, `'omit'` → 108 B with none — hidden, not merely styled away).
  The error runs BOTH ways and the second one is worse, because it
  sends someone hunting a bug that does not exist: `curl https://…/ |
  grep -c skip-link` returns **0** on a host where the skip link is
  shipped and working (excalidraw, 2026-08-31) — it is a Dash
  component in `app.layout`, so React renders it and the served HTML
  never contains it. A fork "verifying the skip link on the wire" with
  curl reports a missing feature that is present. Anything built by
  the layout rather than written into the template is invisible to the
  two artifacts curl can reach; assert it through the layout or a real
  browser, and say which you used.
- Assert the corpus is NON-EMPTY before trusting any negative, and print
  the count beside the result (note 88). A sweep that found nothing and a
  sweep that swept nothing produce the same green, and only one of them
  is evidence. Measured on the template 2026-09-01: its `.flake8`
  excludes `docs/*/`, so `flake8 docs/` exits 0 with a file in `docs/`
  containing `def broken(:` — the linter is not passing that file, it is
  not reading it; `py_compile` sees it at once. Same family, same day: a
  naive substring count read fenced documentation as defects (the
  template seat), a file-scoped grep matched prose ABOUT the defect it
  was hunting (muicharts, clerkhook), a `git show … && diff` printed
  "(empty = same)" on a comparison that never ran (llms), and `pytest …
  | tail -2 && git commit` committed over a red suite because a
  pipeline's exit status is the LAST command's (the template seat, one
  hour after writing the note above). Capture the exit code; count what
  you swept; say both. THIS REPO'S OWN THREE, same family, same round:
  a bare `curl` fetched the crawler document and the sidebar "was
  missing"; a scan for the literal `/admin/` in Dash's layout JSON found
  nothing because Dash escapes the solidus as `/`, making both the
  reassuring and the alarming result meaningless; and a grep whose
  filter could not match a function's own name was read as that
  function's absence and reported upstream as a template gap. A narrow
  search proves presence and never absence.
- And the same family one turn later, worth keeping because it nearly
  shipped a wrong fact into a spec: extracting a package constant with
  `re.search(r"EVENT_FIELDS = \((.*?)\)", src, re.S)` truncated at a `)`
  inside a COMMENT in the middle of the tuple, printed eight of sixteen
  fields, and reported `'ua' present: False` — confidently, with a
  number beside it. Caught only because eight looked too few. When you
  parse a language construct out of source with a regex, check the count
  against something independent (the file, `python -c "from … import X;
  print(len(X))"`, the CHANGELOG) before you believe a negative.

### This repo's own trap

`.claude/` is an ALLOW-LIST ignore, not a blanket one, and the two
fork-authored documents re-included by name are re-included **by
name**. The rule here used to be the inverse — "the .md design docs
in `.claude/` ARE tracked" — and that inversion is how
`.claude/SETTINGS.md` carried a live `k2p_` hub key into this public
repo on its first commit (`2152d49`, found 2026-08-26). Default-deny
plus audited names. If you add something under `.claude/` that
should ship, add the `!` line and say why in the commit.
