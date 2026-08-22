# X402-SYNC-REPORT — dash-model-viewer

## gate-wave

    date:            2026-08-21
    repo:            dash-model-viewer (modelviewer.2plot.dev)
    matrix_row:      "Batch 1 — dash-model-viewer | vendor 1.0.2 + auth wiring
                      + Clerk env block; allowlist gap"
                     (handbook's 1.0.2 reads 1.0.5 per CURRENT STATE)
    source_template: dash-documentation-boilerplate 1.6.4
    head_sha:        abe01a9
    posture:         DARK (PAGE_DEFAULT_TIER=public). NOT flipped — the flip
                     is owner-side and blocked on two allowlists.
    scope:           EXTENDED. This host had never deployed and the entire
                     site was uncommitted; step 0 was a repo reconciliation,
                     not a sync.

### step 0 — repo state found, and what was kept

The 2026-08-16 fleet survey recorded "the whole site uncommitted". That was
accurate and understated. Found on `main`:

    - 193 files of uncommitted work, staged and unstaged
    - the OLD component library staged as deleted (webpack/babel build, the
      generated R / Julia / npm bindings, setup.py, usage_tests/)
    - a NEW hook-based package, untracked (vendored model-viewer UMD +
      hand-authored shim + hand-written Component subclasses)
    - a COMPLETE 10-page documentation site on the boilerplate, untracked
    - 297 tests passing, flake8 clean

So this was not a half-finished edit: it was a finished 1.0.0 rebuild plus a
finished docs site, never committed. **Everything was kept.** The rebuild is
documented in `.claude/ARCHITECTURE.md` (verified against source, not
recalled) and the deletions are deliberate — generated layers with no source,
`deps/` and `inst/` alone at 278 MB each, all recoverable from git history.

Committed as `2152d49` after adding three runtime artifacts to `.gitignore`
that would otherwise have shipped: `visitor_analytics.json` (visitor data,
plus a merge conflict on every deploy), its lockfile, and `.junie/`.

Result: clean, committed `main`. Three commits, one branch, nothing stashed.

### acceptance

    satellite_reporter_shasum:
      boilerplate: a4ebbf26d8dd1ed9f45e3d81f95982d83e639348b722c2602c755be095b6ff2d
      modelviewer: a4ebbf26d8dd1ed9f45e3d81f95982d83e639348b722c2602c755be095b6ff2d
      verdict:     MATCH (byte-identical, as the contract requires)

    vendored_clerk:
      file:    vendor/dash_clerk_auth-1.0.5.tar.gz
      source:  Dash-Clerk-Auth-Hook/dist/ — the dist-only rule, observed
      sha256:  a2f9062e15a69fc79deeaf76fcf1380907a961978db558b2aa227572cb2b74f3
      verdict: MATCH the handbook's required hash
      floors:  clerk-backend-api>=7.0.0,<8 + cryptography>=50.0.0 in
               requirements.txt

    tests:
      before: 297 passed, 1 skipped
      after:  441 passed, 1 skipped
      flake8: clean
      delta:  +144, from ten copied boilerplate test modules

    boot_guards (production-shaped local boot, flask, all CLERK_* set):
      interactive_gate_line: PRESENT —
        "[boilerplate/modelviewer] interactive gate: default tier 'public',
         0 non-public page(s), machine surfaces open by default
         (LLMS_PUBLIC_DEFAULT), access wiring ON, control board at
         /admin/control-board (0 live override(s))."
      visibility_warning: ABSENT
      auth_warning:       ABSENT
      guards_proven_live: YES — all three were deliberately broken and all
        three fired: [visibility] with PAGE_VISIBILITY_FILE unset, [auth]
        with the sign-in redirect unset, and [auth] again with the redirect
        set to `true` (the flag-not-a-destination case, which 404s the Sign
        In button). Each cleared when corrected. The absences above are
        therefore a pass, not a dead check.

    healthz_build_field: VERIFIED — RENDER_GIT_COMMIT=abc123def yields
      {"ok":true,"backend":"flask","dash_version":"4.4.1","build":"abc123def"}

### identity — the caveat resolved, NOT blocked

The kickoff flagged this as possibly BLOCKED ON ART: no `modelviewer.png` on
the CDN, and the repo never favicon-audited. **Audited this pass: the art is
this app's own.**

All eight icon files differ from the boilerplate's by sha256. The mark is an
isometric cube in the brand indigo on a dark rounded square — generated from
geometry by `scripts/make_brand_assets.py`, not resampled from a template PNG.
The webmanifest already names this app. No root `assets/apple-touch-icon.png`
exists, and `templates/index.html` points at `/assets/favicon/apple-touch-icon.png`,
so the root-icon trap does not apply here.

The pixels-before-floor ordering rule is therefore **satisfied**, and the
floor moved in the same pass rather than being held.

### the identity bug this pass actually found

`templates/index.html` was publishing the **boilerplate's** identity to
crawlers, on a page whose `<title>` said dash-model-viewer:

    JSON-LD "description":     the boilerplate's template blurb
    JSON-LD "softwareVersion": 1.2.5   (the boilerplate's version)
    JSON-LD "license":         MIT     (this package is Apache-2.0)
    meta llms-github-repo:     Dash-Documentation-Boilerplate

This is the exact crawler/browser identity drift the network's SEO pass exists
to end, and it would have shipped to Google on the first deploy. Caught by
`tests/test_config.py::test_declared_software_version_matches_constants`, one
of the copied template tests — which is a fair argument for copying them.
All four corrected.

### file set delivered

    byte-copied (template canonical, no local content to preserve):
      lib/satellite_reporter.py   lib/access.py       lib/page_tiers.py
      lib/auth.py                 lib/network_directory.py
      lib/traffic_rollup.py       lib/ad_client.py    lib/health.py
      pages/markdown.py           assets/llms_copy.js

    new to this fork:
      lib/gate_layouts.py   lib/auth_demos.py   lib/agent_key.py
      lib/page_visibility.py   lib/versions.py   pages/control_board.py
      assets/auth_gate.js   assets/auth_gate.css

    new tests:
      test_access.py  test_gate_layouts.py  test_agent_key_route.py
      test_satellite_presence.py  test_control_board.py  test_seo_icons.py
      test_network_directory.py  test_traffic_rollup.py  test_config.py
      test_proxy_scheme.py

    merged (local content preserved):
      lib/constants.py     + PUBLISHER / SAME_AS (HEADER_HEIGHT already present)
      components/header.py + create_clerk_avatar, aria-labels, own GitHub link
      components/navbar.py   Resources section moved last; drawer already present
      tests/conftest.py    + tmp visibility store, /admin excluded from sweeps
      assets/main.css      + the AppShell aside z-index rule
      pages/home.py        + version substitution (hero viewer preserved)
      run.py                 fork point, floor, configure_seo, gate wiring

    the six template features, each verified present:
      1. control board (page_visibility + control_board + test + conftest)  yes
      2. network-standard mobile drawer                                      yes (pre-existing)
      3. aria-labels on every icon-only control; no title= on DMC            yes
      4. ad image aspectRatio box reservation                                yes
      5. _install_signout_delegation + the redirect boot guards              yes
      6. auth_demos.py armed example                                         yes

### fork point

    run.py: os.environ.setdefault("SATELLITE_APP_KEY", "modelviewer")

before any hub-facing import. The reporter is byte-identical by contract, so
its own fallback says "boilerplate" while this fork's other modules say
"modelviewer" — an unset variable would file this site's traffic under the
template's hub row.

### floors moved

    dash-improve-my-llms       2.3.4 -> 2.6.0  (fatal at boot; run.py)
    dash-mantine-components    2.7.0 -> 2.8.0
    clerk-backend-api          (new)   >=7.0.0,<8
    cryptography               (new)   >=50.0.0
    CI in-image assertions     2.3.4 -> 2.6.0  (both sites)

`lastmod:` stamped into all 13 doc frontmatters from each file's real
authoring date (2026-08-08 / 2026-08-09), as literals — never scripted from
mtime at build time, which is the invented-date sitemap 2.6.0 exists to end.

### render.yaml — authored, not reconciled

Was: `runtime: python`, `plan: free`, **no disk**, no Clerk block, no gate
vars, no reporting cadence. The free-plan comments explained at length why
there could be no disk.

Now: `runtime: docker` (matching pannellum/leaflet and this repo's existing
Dockerfile), `plan: starter`, a 1 GB disk at `/var/data` carrying both the
ledger and the control-board store, the full Clerk block, the gate vars, the
reporting cadence, and env rows grouped by which env group supplies them.

Also: `Dockerfile` now `COPY`s `vendor/` before `pip install -r`, since
requirements references the Clerk sdist by relative path.

### CD — the fleet-class bug, at full strength here

The post-deploy wait was gated on `steps.hook.outputs.deployed == 'true'`.
This repo has no deploy hook (fleet decision: Render autoDeploy owns deploy
timing), so **the wait was skipped on every run** and the live battery ran
seconds after the push, against the previous release — invisibly, because the
old build always already passed the old battery.

Fixed per the template: `/healthz` reports `RENDER_GIT_COMMIT`, and the wait
holds until it equals the run's SHA, falling back once with a warning on
builds predating the field.

### deviations

1. **`scripts/make_favicons.py` deliberately NOT carried.** This repo
   generates its mark from geometry (`make_brand_assets.py`), so there is no
   source PNG to resample. A second script writing the same eight paths from a
   different input is how browser icons and crawler icons drift apart
   undetectably — they stay byte-identical until one regenerates and the other
   doesn't. The output layout is the standard one either way, which is all
   that 2.6 discovery and `configure_seo(icons=)` care about.
   `make_brand_assets.py` documents the reasoning in place.

2. **`test_this_app_is_not_its_own_peer` relaxed to self-arm.** This host is
   deliberately absent from the canonical `PEERS` until it deploys, so the
   template's strict "the filter removed exactly one entry" cannot hold. The
   absence assertion — the one that protects a reader — is unchanged; the
   count assertion arms itself once the entry appears upstream.

3. **Local venv rebuilt from sibling venvs**, not PyPI: the sandbox has no
   network. `clerk-backend-api` 7.0.0 and `cryptography` 50.0.0 (exactly the
   declared floors) and `dash-improve-my-llms` 2.6.0 were sourced from
   `dash_pannellum`'s py3.12 venv and `dash-hook-my-ai/dist/`. Production
   installs from `requirements.txt` as normal.

### not done — owner-side or blocked

    - service creation, domain, env groups, identity vars, disk  -> DEPLOY-READINESS.md
    - hub CLERK_ALLOWED_REDIRECT_ORIGINS += modelviewer.2plot.dev  (flip blocker)
    - Clerk dashboard allowed-subdomain for modelviewer.2plot.dev  (flip blocker)
    - QUEUE: network-directory + hub-key registration. This host is
      deliberately absent from the canonical directory until it deploys; add
      it UPSTREAM in the boilerplate, then re-copy verbatim to the fleet.
      Also PULSE_POLL_TARGETS and VERIFIED_APP_IDS on the hub.
    - pip-audit baseline not measured (no network); flip its
      continue-on-error off after the first green run.
    - Docker image never built (no network). First real build is first proof.
    - live verification, and the gate flip, both run after the service exists.
