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

### 10. `CHANGELOG.md` is the PACKAGE's, so site notes go elsewhere

Sync item 12 says to record its reporting consequence — `human_hits` drops
and `bot_hits` rises on adoption day — "in your CHANGELOG under Changed".
The template has no package, so its `CHANGELOG.md` is the site's changelog
and that instruction fits it exactly. Here the file opens "All notable
changes to `dash-model-viewer`" and every entry in it is a package entry;
the docs site's own history has always lived in commit messages and, where
it needs an owner to act, in `DEPLOY-READINESS.md`. Filing a site-analytics
note under `[Unreleased]` would tell a PyPI reader that the component
library changed, which it did not.

So the consequence is recorded in `DEPLOY-READINESS.md` step 11 (owner-
facing, where the Render Branch flip already had to go) and in the commit
message. A future spec item asking for a `CHANGELOG.md` note should be read
the same way: package changes there, site changes in the commit and in
`DEPLOY-READINESS.md`.

### 11. `cd.yml` promote checkout is `actions/checkout@v4`

Item 13's template shape uses `actions/checkout@v7`. Every other checkout in
this repo's workflows is `@v4` and Dependabot's actions group manages that
number here (`.github/dependabot.yml`), so a hand-written `@v7` in one step
would be a version this repo did not choose, in a file the bot is expected
to keep uniform. The item's contract is `fetch-depth: 0`, which is a `with:`
key both majors accept; `tests/test_cd_promotes_release.py` pins the
fetch-depth and not the action version, so nothing about item 13 depends on
the difference.

### 12. `lib/api_reference.py` reads a docstring, because there is no `metadata.json`

Sync item 16 contract (7) generates `/api` from "the installed component
package's metadata (`metadata.json` / `_prop_names` + docstrings)". This
package ships **neither**: the 1.0.0 rebuild removed the generator, the
webpack build and `package.json` (`.claude/ARCHITECTURE.md`), and
`tests/test_no_regeneration.py` fails if any of them return. The template's
`load_package()` returns `[]` for such a package, so `/api` rendered a
569-byte empty shell — which the every-page crawler-body sweep caught.

Ported, not abandoned: `_load_from_python()` reads the exported `Component`
subclasses' `__init__` signature (type, default, required) and their
docstrings' `Keyword arguments:` block (the description) — the same four
columns from the two sources this package actually has, and the same block
format a generated class carries. `metadata.json` is a mechanism; one table
per component with prop · type · default · description is the contract, and
that holds: 32 props on `ModelViewer`, 6 on `Slot`.

`tests/fixtures/fake_dash_pkg/` (the template's fixture, which pins the
metadata.json path) is exempted in `tests/test_no_regeneration.py`'s
`SKIP_DIRS` — it is an INPUT to a test, never a generator's output, and the
guard is about the latter.

SYNC ITEM 18 WIDENED THIS, and the shape changed with it. `lib/api_reference`
now carries the template's THREE-SOURCE ladder — `metadata.json`, then the
committed extract `<pkg>/api_metadata.json`, then the docstrings — and this
fork lands on the third rung permanently. Two fork-side differences remain,
both measured:

- The template's `_from_docstrings` matches `- name (type; optional): desc`
  on ONE line, unindented. This package's docstrings indent the bullet and
  put the description on the NEXT line, so the template's regex returns ZERO
  props here. Source 3 keeps this fork's reader: docstring for names, types
  and descriptions, `__init__` signature for defaults where a signature
  exists. It also has to work on a class that is not a `Component` subclass
  at all — the fleet's `tests/fixtures/docstring_dash_pkg` is exactly that —
  so the DOCSTRING decides membership and the signature only enriches.
- `scripts/build_api_metadata.py` exits if `metadata.json` is absent, which
  is this package's permanent state. Ported to fall back to the same
  docstring reader, so the script's job here is to STAMP a committed date
  rather than to distil a build artifact. `<pkg>/api_metadata.json` is
  committed and listed in BOTH allowlists (MANIFEST.in and pyproject's
  package-data) — outside the wheel it would be present in a checkout and
  missing on the host, which is the split the item exists to close.

`tests/test_api_extract.py` holds what the template's own ladder pin
(`test_nav_contract.py::test_api_reference_falls_back_to_the_committed_
extract_then_docstrings`) cannot know: that pin drives FIXTURES, so it proves
the mechanism; these prove this package. The shipped components come back,
the committed extract still agrees with the docstrings it was built from (it
is a second source of truth that `load_package` PREFERS, so a prop change
that skips the builder silently stops reaching the page), the extract reaches
the wheel, and `/api` carries the rows in both lanes by ROW CONTENT rather
than headings. All four
were mutation-checked before commit — extract removed: two pins red and the
docstring fallback still returns 32+8 props; extract stale: the freshness
pin red; restored: green.

One more line differs and it is a template DEFECT, reported to the seat, not
a divergence to keep: `as_markdown()` escaped `|` in the description cell
only, so a union type (`string | dict`) or an enum default (`'auto' |
'fixed'`) silently splits the Markdown row into extra columns. Every cell is
escaped here. The template has the same bug; it is invisible until a package
has a union-typed prop, and this one has several.

### 13. The nav-contract tests carried this fork's branch — RETIRED at item 18

`tests/test_nav_contract.py` is contract-class this round, and two of its
pins are template-shaped by construction:

- `test_api_page_is_not_registered_when_no_package_is_declared` asserts
  `API_PACKAGES == []`. This site documents `dash_model_viewer`, so the
  contract's OTHER branch is the one that holds: the replacement asserts the
  page registers, plus a second test pinning divergence 12's source.
- the aside and positive-control pins name template pages
  (`/backend-comparison`, `/getting-started`); they name `/quick-start` and
  `/api-reference` here. Same for `tests/test_excluded_links_hidden.py`,
  whose positive control exists precisely so an empty sitemap cannot pass
  the admin-leak assertions vacuously — it has to name a page this host has.

Everything else in both files was the template's, byte for byte.

**RETIRED 2026-08-30 (sync item 18).** The template closed both seams from
its own side at 1.6.41: `test_api_page_follows_api_packages` now branches on
`API_PACKAGES` instead of asserting it is empty, and the aside and
positive-control pins derive their pages from the registry instead of naming
template paths. Both files are byte-identical to the template again, and the
fork-specific assertions moved to `tests/test_api_extract.py`, which is this
repo's own file and not a fork of one of the template's. Kept, marked, because
the last report describes the divergence as live.

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
# Sync item 18: PORTED, not copied. The template's source 3 is a one-line
# regex that returns zero props against this package's indented, two-line
# docstrings, and its builder exits when metadata.json is absent — which is
# this package's permanent state (divergence 12). A byte-copy of either would
# empty /api silently, which is the exact failure the item exists to stop.
- lib/api_reference.py
- scripts/build_api_metadata.py
```

## Posture

What this host ANSWERS, as measured — never as intended. The hub's F4
battery seeded these per-host postures from its own table, which is a
copy of a measurement somebody took once; this block homes them in the
repo that can keep them true, and the hub reads it instead.

Four keys, all optional. An EMPTY block means "the template defaults" —
present, so the absence is a statement. `tests/test_claude_kit.py`
validates the shape (and holds `runtime:` against render.yaml, where the
repo declares one); nothing validates the numbers but a probe, so
re-measure when you change what this host serves:

    ai_bots   the status an AI-crawler UA receives per path, measured
              with a real vendor UA (ClaudeBot, GPTBot — NOT a UA-less
              curl, which is classified separately). A blocked vendor
              gets 403 on the browser document while the agent surfaces
              stay open — that asymmetry is the posture, and it is
              invisible from a browser.
    healthz   `full` (the fleet payload: app, backend, build, geo,
              python, …) or `minimal` (a deliberately reduced body — see
              clerkhook's recorded divergence; the battery's
              python_matches_declared skips with notice there).
    runtime   `docker` or `python` — the Render service runtime, which
              decides whether PYTHON_VERSION is required or forbidden
              (sync spec item 5). This host is `docker`, and declares
              PYTHON_VERSION anyway — divergence 9.
    deploy    `release-branch` — Render deploys `release`, which only
              CD writes after a green matrix (sync item 13); `build` on
              /healthz is HEAD of `release`, and `main` ahead of it is
              an uncertified push pending. ABSENT reads as `main`:
              Render watches main and a push deploys before CI has
              judged it.

Measured on modelviewer.2plot.dev, 2026-08-30T17:38Z, build b1bb93b —
the posture flip (sync item 15, Round 3.4) LANDED. With the ClaudeBot UA
(`Mozilla/5.0 AppleWebKit/537.36 (KHTML, like Gecko; compatible;
ClaudeBot/1.0; +claudebot@anthropic.com)`) and the GPTBot UA
(`…compatible; GPTBot/1.2; +https://openai.com/gptbot`), byte-for-byte
identical for both: `/` 200 (14,065 B, the crawler document),
`/llms.txt` 200 (14,288 B), `/healthz` 200 (215 B). robots.txt carries
no `User-agent: GPTBot`/`ClaudeBot`/`CCBot` stanza and no `Disallow: /`
anywhere — with `block_ai_training=False` the package emits no training
stanza at all, which is the allow shape.

**There is no edge wall on this host**, and this release is what proves
it. The reading before it (2026-08-30T14:15Z, build cf548d0) was
403/200/403 on the wire AND in-process against the same build, with the
same 318-byte denial body both ways — so every 403 here was the app's
`block_ai_training`, and flipping one flag opened all three paths with
no Cloudflare edit. The fleet drop had framed it as two walls, the app's
and an edge rule on `/`; the canary corrected that the same night, and
the owner has since confirmed the WAF AI-bot feature is Enterprise-only
on this plan, so no such rule exists anywhere in the network. History
kept because it corrects a framing, not because the numbers still apply.

```yaml posture
# 2026-08-30T17:38Z, build b1bb93b, ClaudeBot and GPTBot identical
ai_bots: {"/": 200, "/llms.txt": 200, "/healthz": 200}
healthz: full
runtime: docker
deploy: release-branch
```

`deploy: release-branch` is now true on both sides. The repo declared it
when CD's promote step landed; the Render **dashboard's** Branch field is
the other half whenever the service is not Blueprint-managed, and the
owner set it to `release` on 2026-08-30, after three green promotes had
proved the branch holds only certified shas.

The flip changed nothing observable, and that is the expected result, not
a non-event: `main`, `release` and `/healthz` all held `9badadd` across
it, so autoDeploy-from-main and autoDeploy-from-release produce the same
wire. **The road is still unexercised.** The observation that would
distinguish them is the first push that goes RED on `main`: `release`
must not move and `/healthz` must not change. Until that has happened,
this key records an intent that has been configured, not a behaviour that
has been measured — say so in any report that leans on it.
