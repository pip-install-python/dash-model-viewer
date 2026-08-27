# Divergences from the template

Every DELIBERATE difference between this repo and
dash-documentation-boilerplate, with its reason. This file is the
boundary between design and drift:

- Template syncs read this file FIRST and must not "restore" anything
  recorded here.
- A difference not recorded here is treated as drift and will be
  synced away.
- Record the divergence in the SAME commit that creates it — one
  line: what differs, why, and what the template would otherwise do.
- An empty list is a statement too: it means this repo intends to
  match the template exactly.

Scope note, so the list stays readable: **content is not divergence.**
This fork's page set, brand strings, `SITE_H1`, icons, demo models and
docs prose all differ from the template's and always will — that is
what a fork IS. What belongs here is a difference in SHAPE or
CONTRACT: a file whose structure the template would otherwise
overwrite, a template mechanism deliberately not carried, or a
template contract satisfied in a different form.

## This repo's divergences

### 1. `.claude/` allow-list re-includes two fork-authored documents

The template's `.gitignore` block is default-deny under `.claude/`
with three exceptions (`CLAUDE.md`, `settings.json`, `skills/`). This
fork adds two more, **by name**:

    !.claude/ARCHITECTURE.md
    !.claude/GENERATIVE.md

`ARCHITECTURE.md` is the design record for the 1.0.0 hook-based
rebuild and is cited from `README.md` and from
`dash_model_viewer/_components.py` — untracking it would break two
live references. `GENERATIVE.md` holds the paid-model safety
constraints for `docs/generative-3d`, which a contributor needs
before touching that page.

Both were audited for secrets at re-inclusion. The direction matters:
this is default-deny plus two audited names, never the inverse. The
rule here USED to be the inverse — "the .md design docs in `.claude/`
ARE tracked" — and that is exactly how `.claude/SETTINGS.md` carried
a live `k2p_` hub key into this public repo on its first commit
(`2152d49`, found during this sync, 2026-08-26). `SETTINGS.md`,
`proposed-user-settings.json` and `DOCS-PLAN.md` were untracked in
the same change; the key itself is owner-side rotation, because git
history keeps it.

A sync must not "simplify" this back to the template's three lines.

### 2. `tests/test_python_version.py` is JOB-SCOPED, not file-scoped

SYNC-1.6.22-1.6.27 item 5 ships this file as session-class, and its
template form asserts against *every* `python:` line in `ci.yml` —
one matrix main, one set of literal pins. This repo has **two** CI
lanes (divergence 3), so the template's form fails here by
construction. The pins are therefore scoped to the job that owns each
number:

- the SITE lane (`test`, the one that varies `backend`) is held to
  the fleet Python and the three-wide window around it;
- the WHEEL lane (`package-matrix`) is exempt, and the exemption is
  earned by two extra pins — it must still cover its own
  `requires-python` floor, and it must still build on the fleet
  Python, because the Dockerfile installs this wheel and serves it
  there.

A third added pin holds `pyproject.toml`'s trove classifiers to the
fleet Python: CI proves 3.14 on every push, so claiming only through
3.13 would understate a fact this repo already establishes.

The item's CONTRACT — one Python everywhere the SERVING interpreter
is encoded — is fully ported. What is not ported is the assumption
that the serving interpreter is the only Python `ci.yml` names.

### 3. `.github/workflows/ci.yml` carries a `package-matrix` job

This repo is a Dash component library *and* its documentation site.
The template is only ever a site, so it has no equivalent lane. The
extra job builds the wheel and installs it across `requires-python`
(3.9 floor → the fleet Python), on a sweep of pinned Dash versions.

Consequence for syncs: `ci.yml` here can never be a byte-copy target,
and any spec item that counts jobs, matrices or python pins in
`ci.yml` must be read job-wise. See divergence 2.

### 4. No `published_name`, and no call site in `pages/markdown.py`

SYNC-1.6.10-1.6.16 item 8 gives the machine-lane home an h1 equal to
the site brand. The template implements it with
`lib/page_visibility.published_name()` called from `pages/markdown.py`.

Here `/` is served by `pages/home.py` from `pages/home.md`, whose
first line already **is** `SITE_BRAND`, so the preamble and dimll's
injected header agree with no indirection. Porting the template's
shape would add a function whose interesting branch (`path == "/"`)
can never be taken, because `markdown.py` never serves `/`.

This is the batch-1 correction to that item's shape-dependence,
applied (pannellum's hand-written home set the precedent, 2026-08-25).
The contract is pinned on the wire, not by the function's existence:
`scripts/network_smoke.py::llms_txt_identity` asserts `/llms.txt`'s
first line equals `SITE_H1`, and the every-page sweep in
`tests/test_pages.py` asserts exactly one h1 on `/`.

### 5. `tests/test_requirements.py` in place of `tests/test_runtime_imports.py`

Same defect, two implementations, and the template's is the
descendant: its docstring opens "A fork of this template died in
production on `ModuleNotFoundError: No module named 'PIL'`" — that
fork is this one (2026-08-21). `test_requirements.py` was written
here in response, and the template later upstreamed the idea in its
own form (import-resolution against a clean environment, versus this
file's `packages_distributions()` mapping against `requirements.txt`).

Kept as-is for now: no spec item asks for the swap, and the two files
answer slightly different questions. **Next-pass work**, not
divergence-forever — the honest end state is one of them, and the
template's is the more thorough. Recorded so a sync does not land
both and leave the duplication unexplained.

### 6. `scripts/make_favicons.py` deliberately not carried

This repo generates its mark from geometry
(`scripts/make_brand_assets.py`), so there is no source PNG to
resample. A second script writing the same eight paths from a
different input is how browser icons and crawler icons drift apart
undetectably — they stay byte-identical until one regenerates and the
other does not. The output layout is the standard one either way,
which is all that dimll discovery and `configure_seo(icons=)` read.

### 7. `Dockerfile` ends with `RUN pip install --no-deps .`

The site documents the package in THIS checkout, never PyPI. The
template has no package to install, so this line has no upstream
counterpart. It is also why a component change and its documentation
ship in one commit.

### 8. `DEPLOY-READINESS.md` stays tracked while `X402-SYNC-REPORT.md` does not

The kit's session-document block (item 6) names `X402-SYNC-REPORT.md`,
`HANDOFF-*.md`, `KICKOFF-*.md` and `kickoff/`; all four are ignored
here and the tracked sync report was untracked in this change.
`DEPLOY-READINESS.md` is deliberately kept: it is not session
narrative but a live list of owner-side items this repo still needs
(disk attachment, the two Clerk allowlists blocking the gate flip).
When those close, it goes.

### 9. `render.yaml` declares `PYTHON_VERSION` on a `docker` runtime

The fleet rule as of the 2026-08-26 drop branches on runtime:
`runtime: docker` → `PYTHON_VERSION` **absent**, and pinned absent;
`runtime: python` → `PYTHON_VERSION` `"3.14.x"`. This service is
`runtime: docker` (render.yaml, and the reason is divergence 7: the
image installs the package from this checkout) and declares the
variable anyway, at `"3.14.7"`.

What that line does here, precisely — measured, not assumed:

- **The deploy ignores it.** Render reads `PYTHON_VERSION` for native
  Python runtimes; on a docker service the `FROM python:3.14-slim`
  tag is the interpreter, which is why `/healthz` reports 3.14.7
  whatever this says.
- **The battery ignores it.** `network_smoke.declared_python_minor()`
  parses the Dockerfile's FROM minor, so `python_matches_declared`
  would stay green if this line read 3.9.
- **One local test reads it**:
  `test_python_version.py::test_render_yaml_agrees_with_the_image`.

So it is a declaration with no consumer on the deploy path. It is
kept for one reason, written at the line itself: a future revert to
`runtime: python` would otherwise hand the service a default
interpreter that no gate ever tested, and the failure mode of that
is silent. The cost of keeping it is the standard cost of inert
config — someone may one day "fix" the Python version by editing a
line that cannot change anything.

Recorded rather than resolved: the earlier kickoff's per-fork table
already named the wave-3 render.yaml rule a divergence for this fork
and no entry was ever written, which is the gap this closes. Whether
the fleet prefers the branch rule's `absent` here is an ops-seat
call, not a fork-local one — flagged in that pass's report. If the
answer is absent, the change is one env line plus inverting the pin
above, and this entry retires.

## Retired

Marked, not deleted — older reports still describe these as live.

### R1. `test_this_app_is_not_its_own_peer` relaxed to self-arm — RETIRED 2026-08-21

At gate-wave time this host was deliberately absent from the
canonical `PEERS` directory until it deployed, so the template's
strict "the filter removed exactly one entry" could not hold, and the
count assertion was written to arm itself once the entry appeared
upstream. Template 1.6.5 added `modelviewer` to
`lib/network_directory.py`, the file was re-copied verbatim in the
round-2 pass, and the strict form has been green since. No divergence
remains; `X402-SYNC-REPORT.md` (now untracked) describes it as live.

## Byte-owned paths

Paths this fork owns byte-for-byte. The F3b fan-out never overwrites
a path listed here; everything else in the spec's `sync-verbatim`
block is the template's to update mechanically. Prose above explains
divergences; this block is the machine answer.

Repo-relative paths, one per line, `#` comments, no `..`; exactly one
block. An EMPTY block means "the template owns every sync-verbatim
path here" — present so the absence is a statement. When the block
exists it is authoritative; a fork without it gets the conservative
mention heuristic (over-flags, never restores).

Re-audited 2026-08-26 at template 1.6.29 (`5589318`), the fourth spec
consumed here. All six current `sync-verbatim` paths — the three
skills, `tests/test_claude_kit.py`, `.github/dependabot.yml`,
`tests/test_auth_demos.py` — are byte-identical to the template here
(two of them refreshed by the F3b fan-out in `608fcea`) and are NOT
listed: the template owns them.

`scripts/smoke_live.py` is deliberately NOT listed either, though one
line of it is fork-specific (the usage host in its docstring). Item 6
is contract-class as of 1.6.29 precisely because each fork's own
`tests/test_smoke_live.py` stubs its interface, so the fan-out cannot
reach it; and if a later spec ever promotes it back to cargo, a
byte-copy would cost this fork one docstring line and gain it every
upstream fix. Fencing it to protect that line would trade a real
update channel for a cosmetic one.

One path IS listed, and it is a pre-registration rather than a
correction. `tests/test_python_version.py` is session-class in
SYNC-1.6.22-1.6.29 too (re-checked 2026-08-26: still absent from that
spec's `sync-verbatim` block), so the fan-out cannot touch it yet; the
moment a later spec promotes it to block cargo, a byte-copy would
silently replace this fork's job-scoped pins (divergence 2) with the
template's single-lane form and hand the next session a red suite to
diagnose. Listing it now costs nothing and answers that in advance —
the block's own question is "which paths does this fork own
byte-for-byte", and this is one.

```yaml byte-owned
# See divergence 2 — two CI lanes, so the pins here are job-scoped.
- tests/test_python_version.py
```
