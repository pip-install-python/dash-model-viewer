# DEPLOY-READINESS — modelviewer.2plot.dev

**This host has never deployed.** Everything in this repo is authored and
locally verified; nothing here has been checked against a running service,
because there isn't one yet. This document is the owner-side half.

Repo state at handback: clean committed `main` at `abe01a9`, 441 tests
passing, flake8 clean, shipping **dark** (`PAGE_DEFAULT_TIER=public`).

The steps are ordered. Steps 1–5 stand the service up. Step 6 is the
first-deploy verification. Steps 7–9 are the network registration that
nothing will tell you it is missing. Step 10 is the gate flip, and it has its
own blockers.

---

## 1. Create the service

Create a Blueprint from this repo. `render.yaml` is authoritative and declares:

| | |
|---|---|
| name | `dash-model-viewer-docs` |
| runtime | `docker` (`./Dockerfile`, context `.`) |
| plan | `starter` |
| region | `oregon` |
| health check | `/healthz` |
| autoDeploy | `true` |

**Why Docker and not `runtime: python`:** the site installs the package from
this checkout (`pip install .`) and the package ships a ~1 MB vendored
model-viewer bundle as package data. Docker makes that install order
reproducible, and CI's container battery then tests the same image the service
runs. It matches the reference satellites (pannellum, leaflet).

## 2. Attach the disk — and then verify it attached

`render.yaml` declares a 1 GB disk at `/var/data`. **A declaration attaches
nothing.** The pilot host ran for weeks with the block present and no disk:
the app happily `mkdir`'d `/var/data` on the container filesystem, and every
deploy silently wiped both the control board and the analytics ledger.

Confirm in the dashboard's **Disks** tab, or trust the boot guard — see step 6.

The disk carries **both** `TRAFFIC_ANALYTICS_FILE` and `PAGE_VISIBILITY_FILE`.
Accepted trade-off, fleet-wide: a disk-backed service restarts with a brief
blip on deploy rather than a zero-downtime overlap. Correct for a docs site,
~$0.25/mo.

## 3. Link the three env groups

Do this at service creation. It delivers the shared values without retyping.

| Group | Supplies |
|---|---|
| `2plot-network-shared` | `CROSS_APP_WEBHOOK_SECRET`, `NETWORK_BULLETIN_URL` |
| `2plot-satellite-reporting` | `SATELLITE_REPORT_INTERVAL_S`, `TRAFFIC_ANALYTICS_FILE`, `PAGE_VISIBILITY_FILE` |
| `2plot-clerk-satellite` | the whole `CLERK_*` block, incl. the sign-in redirect |

## 4. Set the four per-service identity vars

A group cannot supply these — they are what makes this host *this* host.

```
SATELLITE_APP_KEY = modelviewer
APP_BASE_URL      = https://modelviewer.2plot.dev
AD_APP_ID         = modelviewer
SESSION_SECRET    = <generated, UNIQUE to this service — never copy another host's>
```

`run.py` `setdefault`s `SATELLITE_APP_KEY` to `modelviewer` as the fork point,
so an unset variable degrades to the right value rather than to the template's.
Set it anyway: the code default exists to close a gap, not to be relied on.

> **Blueprint env is not service env.** Render applies `render.yaml`'s
> `envVars` on a Blueprint **sync**, not on an autoDeploy from a git push.
> Anything in that file must **also** exist on the service in the dashboard.
> This has bitten the fleet more than once, and it is invisible: the code is
> wired, the deploy is green, and the feature is simply off.

## 5. DNS

Point `modelviewer.2plot.dev` at the service with a CNAME to the Render
hostname shown once the domain is accepted. Render provisions the certificate
when the CNAME resolves.

Until it resolves the service is reachable only on `*.onrender.com`, while
every canonical URL already advertises `modelviewer.2plot.dev`. That is
intentional — link equity consolidates onto the custom domain instead of
competing with it.

---

## 6. First-deploy verification

**The deploy log is the acceptance check: three absences and one presence.**

| | Expect |
|---|---|
| `[boilerplate/modelviewer] interactive gate: …` | **PRESENT** |
| `[visibility] WARNING …` | **ABSENT** — its presence names exactly which half of the disk wiring is missing |
| `[auth] WARNING …` | **ABSENT** |
| any dependency-floor `RuntimeError` | **ABSENT** |

Both guards were proven live in this pass — deliberately broken, both fired,
then cleared when the config was corrected. Their absence is a pass, not a
dead check.

Then, over HTTP:

```bash
curl -s https://modelviewer.2plot.dev/healthz          # {"ok":true,...,"build":"<sha>"}
curl -s https://modelviewer.2plot.dev/llms.txt         # 200 prose
curl -s https://modelviewer.2plot.dev/llms-small.txt   # 200
curl -s https://modelviewer.2plot.dev/llms-full.txt    # 200
curl -si https://modelviewer.2plot.dev/api/agent-key   # 204 anonymous
python scripts/network_smoke.py --base-url https://modelviewer.2plot.dev
python scripts/smoke_live.py https://modelviewer.2plot.dev
```

`"build"` in `/healthz` is the commit the running instance was built from. CD
holds until it matches the pushed SHA — that is what stops the live battery
verifying the *previous* release, which is what it did on every run before
this pass.

**Declared-vs-live env diff.** Before trusting anything, diff `render.yaml`'s
`envVars` against the service's actual environment. The pilot measured *seven*
declared variables absent live — including `PAGE_VISIBILITY_FILE`. No test can
see this class of fault; only the diff can.

---

## 7. Register with the network — three places, all silent when missed

**a. Hub health polling.** On 2plot.ai, add to `PULSE_POLL_TARGETS`:

```
modelviewer=https://modelviewer.2plot.dev/healthz
```

**b. The canonical network directory.** `modelviewer.2plot.dev` is
**deliberately absent** from `lib/network_directory.py`'s `PEERS` — the
directory does not advertise a host that answers nothing. This repo's copy is
byte-verbatim from the boilerplate and must **not** add itself locally; that is
exactly the drift the 2026-08-20 sweep found (seven different lists across nine
repos).

Once this host is live, add it **upstream in the boilerplate**, then re-copy
verbatim to the fleet. `tests/test_network_directory.py::test_this_app_is_not_its_own_peer`
self-arms: it pins the strict count automatically once the entry appears.

**c. Verified app IDs.** Add `modelviewer` to the hub's `VERIFIED_APP_IDS`.

## 8. Confirm presence reporting

Within ~100s of a real visit, this host's row on the hub board should move to
`● live`. If it doesn't, `CROSS_APP_WEBHOOK_SECRET` is the first thing to
check — the boot log says `[satellite-traffic] disabled` when it is unset.

## 9. Turn the pip-audit gate on

`.github/workflows/ci.yml`'s `pip-audit` job is `continue-on-error: true`.
`requirements.txt` now carries the fleet security floors
(`clerk-backend-api>=7.0.0,<8`, `cryptography>=50.0.0`) that clear the four
advisories a 5.x SDK re-reported forever. **The first green audit run is the
signal to flip that flag off**, so new advisories actually gate.

I could not run pip-audit in this pass — the sandbox has no network — so this
is unverified rather than done.

---

## 10. The gate flip — blocked until two allowlists are updated

The site ships **dark**: `PAGE_DEFAULT_TIER=public`. Flipping it to `auth`
gates every docs page that doesn't pin its own tier. **Do not flip until all
three of these pass**, or users will sign in successfully and be stranded on
2plot.ai with no error anywhere:

1. **Hub redirect allowlist.** `modelviewer.2plot.dev` is **missing** from
   2plotai's `lib/auth.py` origin tuple (re-verified 2026-08-19 against
   `2ebbed4`: 24 origins, this host not among them). Add it via the hub's
   `CLERK_ALLOWED_REDIRECT_ORIGINS` env — no hub deploy needed.
2. **Clerk dashboard.** Add `modelviewer.2plot.dev` to the allowed-subdomains
   list for the 2plot.dev satellite.
3. **One real round trip.** From this host: sign-in card → onboarding → back
   here, signed in.

Also confirm enforcement is live *before* the flip — a host that flips without
the access wiring live will prerender gated prose to crawlers.

**Rollback is env-only:** set `PAGE_DEFAULT_TIER=public` again. No code revert,
anywhere.

`/` and `/quick-start` are pinned public in `run.py` and never inherit the
gate. A docs site may gate its reference pages behind an account; it may not
gate the page that teaches someone to install the package.

`LLMS_PUBLIC_DEFAULT` stays `1` until the network's crawl-demand window closes.

---

## 11. Point Render at `release` — DONE 2026-08-30

The host **is** live now (steps 1–6 happened; the "never deployed" framing at
the top of this document predates that and is kept only so the ordering above
still reads).

**The owner set the dashboard's Branch to `release` on 2026-08-30**, after
three green promotes (`b1bb93b`, `576880d`, `9badadd`) had shown the branch
receives only certified shas. Kept rather than deleted because the next
person to stand a service up needs the ordering, and because the last
paragraph is still an open measurement.

Sync item 13 moved the deploy road: `render.yaml` now declares
`branch: release`, and `.github/workflows/cd.yml`'s `deploy` job is the only
thing that writes `release` — a fast-forward push of the run's own sha, after
the CI matrix is green. A push to `main` is a candidate, not a deploy.

**`render.yaml`'s `branch:` is only authoritative if this service is
Blueprint-managed.** If it is not, the dashboard's **Branch** field is the
switch, and only the owner can flip it:

> Render dashboard → `dash-model-viewer-docs` → Settings → Build & Deploy →
> **Branch**: `main` → `release`.

Do it **after** the first promote step has run green, so `release` exists and
holds a certified sha. Before the flip, Render still builds `main`: the wire
follows main while the repo (and `DIVERGENCES.md`'s posture fence) says
`release`.

**STILL OPEN — the road is configured, not yet measured.** Neither the flip
nor any run so far can tell the two roads apart: `main`, `release` and
`/healthz` have held the same sha at every step, so autoDeploy-from-main and
autoDeploy-from-release produce an identical wire. Measured across the flip
itself on 2026-08-30: all three at `9badadd` before and after, every path
200. The discriminating observation is **the next push that goes red on
main** — `release` must not move and `/healthz` must not change. Whoever
sees the first red CD run on this host should record that, because it is the
only thing that turns this from a setting into a fact.

### The analytics numbers step on the 2.8.0 deploy

Same round, and it is not a defect: `human_hits` **drops** and `bot_hits`
**rises** on the first day this ships. `lib/analytics_tracker.py` no longer
carries its own User-Agent list — it delegates to
`dash_improve_my_llms.classify()` — and UA-less and library clients (`httpx`,
`Go-http-client`, `node-fetch`, an empty User-Agent) move from the human lane
to the crawler lane, where they always belonged. The old list also filed
ClaudeBot, Anthropic's *training* crawler, as "search". The hub's
day-over-day view will show the step. That is the number becoming true.

---

## Known gaps, stated plainly

- **Nothing here is live-verified.** The service does not exist yet.
- **The Docker image was never built.** The sandbox has no network, so
  `pip install` inside a build could not run. The Dockerfile is reviewed and
  the `vendor/` copy ordering is fixed, but the first real build is the first
  proof.
- **pip-audit not run** (step 9), same reason.
- **`ANTHROPIC_API_KEY` is optional.** The Scene Director page degrades to a
  written explanation without it. The *package* never depends on a model
  provider; only the docs site does.
- **A half-installed dash-clerk-auth kills the boot**, it does not degrade.
  The package registers a setuptools entry point, so Dash imports it at
  construction whether or not any `CLERK_*` key is set. `requirements.txt`
  pins the tarball and both security floors together for exactly this reason —
  never install one without the others.
