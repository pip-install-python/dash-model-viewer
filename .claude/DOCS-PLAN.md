# modelviewer.2plot.dev — documentation plan

> **STATUS (built).** The site exists: 10 pages on the boilerplate, booting on
> Flask, 206 tests green. What follows is the plan as written *plus* what
> actually happened, because two of the predictions were wrong and the
> corrections are the useful part.

Shape is the network standard two-file page: `docs/<slug>/{<slug>.md, example.py}`
(verified against `2plot_leaflet/docs/` and `dash-documentation-boilerplate/docs/`).
`SITE_BRAND = "dash-model-viewer — interactive 3D models and AR for Dash"`,
app id `modelviewer` everywhere.

## Seeding

The six examples in `pip-docs+/docs/dash_model_viewer/` are free regression
fixtures — they are the only proof we have of what 0.0.1 could do. Each one
should **shrink measurably** once output props exist. That shrinkage is the
headline evidence for the rebuild, so record before/after line counts:

| Seed example | Lines today | Why it shrinks |
|---|---|---|
| `quick_start_example.py` | 24 | barely — it is already minimal |
| `dynamic_switching_example.py` | 38 | slightly |
| `ar_customization_example.py` | 47 | `Slot` replaces three custom-AR props |
| `basic_annotations_example.py` | 92 | `Slot` replaces list-of-dicts hotspots |
| `dynamic_dimensions_example.py` | 168 | `model_info.dimensions` replaces the JS bounding-box maths |
| `camera_views_example.py` | 230 | `camera` + `Slot.n_clicks` replace the whole clientside layer |

**Measured.** `camera_views_example.py` was **230** lines (not 231) and the
rewrite at `docs/camera-and-views/camera_views.py` is **47** — a 4.9x
reduction, and no JavaScript at all. That was the bet the whole rebuild rested
on, and it paid.

Two corrections to the plan above:

- The seed examples were **not** used as regression fixtures. They are written
  against the 0.0.1 API, which no longer exists, so porting them would have
  meant rewriting them anyway. `docs/` is written fresh; the seeds' value was
  the *line counts* above, as the before-measurement.
- The four broken assets and the 0-byte CSS were not "fixed" either — the new
  pages reference none of them. `assets/` now contains only the site's own
  CSS/JS and the favicon set.

## Assets — fix, do not inherit

Broken in the seed and must not be copied forward:

- `hand.png` — referenced, missing
- `ThorAndTheMidgardSerpent.webp` — referenced, missing
- `dimensions_styles.css` — referenced, missing
- `dynamic_hotspots.css` — referenced, missing
- `model-viewer-styles.css` — exists, **0 bytes**

`.glb` demo models (~40 MB) go to `cdn.2plot.ai`, never into the repo. See
`ARCHITECTURE.md` §8.3 — the licence audit blocks this, it is not a formality.
Replacements: Google's model-viewer sample assets and the Khronos glTF Sample
Models (both permissively licensed, both attributable).

## Page order

Ordering is deliberate: parity and events come *early*, because they are what
1.0.0 is for. A reader who bounces after three pages should have learned the two
things the old docs could not teach.

**Built**, in this order (10 pages incl. home). `scene-director` is NOT built
— it needs an API key and the `auth` tier; see `GENERATIVE.md`.

| # | Slug | Carries |
|---|---|---|
| 1 | `home` | What it is, install, the 8-line quick start, the AR fix in one sentence |
| 2 | `quick-start` | `src` / `alt` / `camera_controls`, assets vs absolute URLs |
| 3 | `attributes-and-parity` | **`attributes` dict + `mv_*`.** The "works with model-viewer 5.x without a release" page |
| 4 | `events-and-callbacks` | All seven output props; `camera_change_debounce`; the echo-loop trap, shown failing then fixed |
| 5 | `camera-and-views` | The shrunk `camera_views_example` |
| 6 | `slots-and-hotspots` | `Slot`; migration from list-of-dicts |
| 7 | `augmented-reality` | `ar_modes`, the `basic_annotations` bug, per-platform behaviour, `ar_status` / `ar_tracking` |
| 8 | `model-switching` | `src` swapping, variants, `model_info.variants` |
| — | `dimensions` | **Not built as its own page.** `model_info.dimensions` is demonstrated on `events-and-callbacks` instead; a whole page for one prop was not earning its place |
| 10 | `api-reference` | Full prop table, every event payload, precedence rules |
| 11 | `migrating` | 0.0.1 → 1.0.0, prop-by-prop |
| — | `scene-director` | **Not built.** Generative; needs a key + the `auth` tier. See `GENERATIVE.md` |

## Page-level rules (from LESSONS.md, non-negotiable)

- `image_url=` **and** `description=` at **every** `register_page`. One missing
  and Dash emits `content=""`, and the empty tag — later in document order —
  wins with scrapers.
- `templates/index.html` declares only what Dash omits. Verify with
  `grep -n '{%' templates/index.html`: every hit must be a real placeholder
  line, never inside an HTML comment.
- Social card is a hard gate: generate → upload by hand to
  `cdn.2plot.ai/github_assets/modelviewer.2plot.dev.png` → verify 200 and IHDR
  1200×630 **by reading bytes** → only then deploy.

## Docs-site specific hazards for this component

1. **Every page loads ~1 MB of vendored JS** (ARCHITECTURE §5) plus a `.glb`.
   A docs site that renders six viewers on one page is a 20 MB page. Cap it:
   one viewer per page, `poster` on all of them, and `loading="lazy"` below the
   fold.
2. **AR cannot be demonstrated on desktop.** Every AR page needs an honest
   "scan this QR code on a phone" path, or it documents a feature no reader can
   see. This is also the only way the `arModes` fix is *visible* rather than
   asserted.
3. **`/llms.txt` stays public**, satellites hold no key material.


---

## What the boilerplate's own tests caught

Worth recording, because each was a silent defect that a hand-written suite
would not have looked for:

1. **`package.json`** — the boilerplate ships dash-mantine-components' build
   file. It is unused here (DMC installs from PyPI) and it tripped the
   package's own anti-regeneration guard. Deleted, along with the Dockerfile's
   `npm install` step.
2. **`assets/favicon.ico` referenced but absent** — the template pointed at a
   file that was never copied. The guard exists because the deploy builds from
   git, so a file present on disk and missing from the index 404s only in
   production.
3. **`theme-color` drift** — changing the manifest's colour without changing
   `templates/index.html` leaves the browser chrome and the install splash
   disagreeing.
4. **The tagline default in `make_social_card.py`** was a hard-coded
   boilerplate string, so every fork rendered a correctly-branded headline over
   the *boilerplate's* description. Now derived from `SITE_BRAND`, like
   `--brand` already was. **This one is a fix to send upstream.**
5. **`tests/__init__.py`** (a 0.0.1 leftover) made pytest import `conftest`
   twice under two names, so the session-scoped temp-state directory existed
   twice and the analytics-ledger test compared two different paths.

## The brand rule flips

`tests/test_site_identity.py` asserted `package name NOT in SITE_BRAND` — the
*template* rule, because nobody installs a template. Every library satellite
does the opposite (STANDARD §1): the package name comes first. The assertion is
inverted here with that rationale in the test body, and both halves stay
pinned: brand leads with the package name, byline stays out of it.
