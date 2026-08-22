# Settings proposal — where each value belongs, and why

`.claude/proposed-user-settings.json` is a **proposal**, not live config. Nothing
reads it. Move its contents into a real settings file once you agree with the
split below. JSON carries no comments, which is why the reasoning is here.

---

## The key must not go in the committed file

You asked for `https://2plot.dev/pip/llms.txt?key=k2p_…` in settings. Three
measurements say to do it differently:

**1. `.claude/settings.json` is committed.** `git check-ignore` resolves
`.claude/settings.local.json` (via `~/.config/git/ignore:1`) but **not**
`.claude/settings.json`. A key placed there lands in a public repo.

**2. WebFetch permissions match on domain, not URL.** The rule is
`WebFetch(domain:2plot.dev)`. Putting a full URL in a permission rule buys
nothing — the key would be decoration in a file that publishes it.

**3. The key is not needed to read that URL, and it is not a content gate.**
Measured:

| Request | Status | Bytes |
| :-- | :-- | --: |
| `/pip/llms.txt` | 200 | 12,026 |
| `/pip/llms.txt?key=k2p_…` | 200 | 14,346 |

The 2,320-byte difference is **entirely the key being appended to ~19 outbound
links** — the site index, and each component's own `llms.txt`. Same prose, same
sections. So the key is a *propagation / attribution* token: the hub threads it
through its own links so an agent that follows them stays identified.

That makes it a credential (it identifies you) with no read-gating value. It
belongs in a gitignored file, and the settings file only needs the domain.

### Where it goes

`.claude/settings.local.json` — gitignored, personal:

```json
{
  "env": {
    "PIP_DOCS_LLMS_KEY": "k2p_a1313d37249b8a14_f9813c8200622c4d21b2ee59ff7ca309"
  }
}
```

Then fetch `https://2plot.dev/pip/llms.txt?key=$PIP_DOCS_LLMS_KEY`. `.env`
works equally well and is already gitignored here — pick one, not both.

---

## Two separate mechanisms, both needed

These are easy to confuse and they gate different things:

| Setting | Gates | Example |
| :-- | :-- | :-- |
| `permissions.allow` → `WebFetch(domain:X)` | the **WebFetch tool** | reading the hub's docs |
| `sandbox.network.allowedDomains` | **egress from sandboxed Bash** | `curl`, `pip install`, `git fetch`, `docker pull` |

Allowing a domain for WebFetch does not let `curl` reach it, and vice versa.
The proposal sets both, with `api.anthropic.com` and the package registries in
the sandbox list only (nothing WebFetches them).

---

## `allowLocalBinding: true` — earned, not speculative

This session hit it. The docs container was built, booted, and reported
`(healthy)` by Docker's own healthcheck, but every host-side probe failed:

```
[FAIL] healthz_ok — URLError: <urlopen error [Errno 1] Operation not permitted>
0 passed, 9 failed
```

`scripts/network_smoke.py` could not reach `http://localhost:8551` because the
sandbox blocks local binding by default. The battery had to be run from *inside*
the container with `docker exec` instead — which works, but is not what the
script is for, and it silently looks like an app failure rather than a sandbox
one.

Without this, the container-boot gate cannot be run the way CI runs it.

---

## What is deliberately NOT here

**`env: { "ANTHROPIC_API_KEY": "" }`.** Tempting as a cost guard — an agent
that cannot see the key cannot spend money. It is not in the proposal because
it would also blank the key for `python run.py` launched from this session, so
`/scene-director` would be silently off during development and look broken.

The guard belongs where it is precise, and it is already there:
`tests/conftest.py` blanks `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN` and
`GEMINI_API_KEY` before anything imports the app, and
`test_the_suite_cannot_spend_money` asserts it. That covers the real risk — a
test run billing you — without breaking the dev server.

If you want a harder stop, add it to `.claude/settings.local.json` (personal,
gitignored) rather than the committed file, so a contributor's setup is not
silently different from yours.

**`sandbox.network.strictAllowlist`.** Would make unlisted hosts fail
deterministically instead of prompting. Project settings are **ignored** for
this key — it is honored only from user, managed, or `--settings` scope. Put it
in `~/.claude/settings.json` if you want it.

**Anything already in `~/.claude/settings.json`.** Your user settings already
carry the credential-file denies, the `ask` rules for `git push` / `npm publish`
/ `gh release`, `sandbox.enabled`, and the `docker *` / `git *` sandbox
exclusions. Settings merge user → project → local, so none of that is repeated
here. The proposal only adds what is specific to this repository.

---

## Applying it

```bash
# team-wide, committed — domains and command allowlist only
cp .claude/proposed-user-settings.json .claude/settings.json

# personal, gitignored — the key
cat > .claude/settings.local.json <<'JSON'
{ "env": { "PIP_DOCS_LLMS_KEY": "k2p_…" } }
JSON
```

Then verify the file parses — a malformed settings.json **silently disables
every setting in it**, with no error:

```bash
jq -e '.permissions.allow | length' .claude/settings.json
```
