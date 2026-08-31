"""Shared fixtures — boot the real app once, then interrogate it.

The suite deliberately exercises `run.py` itself rather than a stripped-down
app assembled for testing. Nearly everything worth catching here lives in the
wiring: registration order, which middleware runs first, whether a page's
prose survived to the response. A test app that re-implements that wiring
tests the re-implementation.

Backend selection follows `DASH_BACKEND`, so the same suite runs against
Flask, FastAPI and Quart in CI. `client` normalises the three test clients
behind `.get(path, user_agent=...) -> (status, text)`.

SECRETLESS, AND ORDER MATTERS. The suite runs against the app exactly as CI's
zero-secret container does: no Clerk keys (auth falls open, non-public tiers
still deny), no `CROSS_APP_WEBHOOK_SECRET` (the hub client reports itself
disabled and the traffic reporter never starts a thread), and the analytics
ledger in a temp dir. The zero-secret boot is itself the first invariant —
every fail-closed assertion in tests/test_access.py depends on it.

The env block below therefore has to run BEFORE anything imports `run.py`,
because `lib/backend.py` calls `load_dotenv()` during that import and a
developer's local `.env` would otherwise flip the app into a configured
posture. `load_dotenv()` never overrides an existing key, so pinning each
secret to `""` here (falsy to every `os.getenv(...) or None` reader in `lib/`)
neutralises the file without deleting it. In CI there is no `.env` at all and
this is belt-and-braces. Same pattern as 2plotai and pip-docs+.
"""

from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# --- 1. Neutralise every secret (must precede any import of run.py) ---------
SECRET_ENV_KEYS = (
    "CLERK_SECRET_KEY", "CLERK_PUBLISHABLE_KEY", "CLERK_SIGN_IN_URL",
    "CLERK_SIGN_UP_URL", "CLERK_FRONTEND_API", "CLERK_WEBHOOK_SECRET",
    "CLERK_IS_SATELLITE", "CLERK_SATELLITE_DOMAIN", "SESSION_SECRET",
    "FLASK_SECRET_KEY", "CROSS_APP_WEBHOOK_SECRET", "NETWORK_BULLETIN_URL",
    "DATABASE_URL", "AD_DATABASE_URL",
    # Model-provider keys. `lib/backend.py` calls load_dotenv(), so a developer
    # with a real key in .env would otherwise have the suite make BILLED API
    # calls — silently, and on every run. Blanked here so the generative page
    # fails closed in tests exactly as it does on a host with no key set.
    "ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "GEMINI_API_KEY",
)
for _key in SECRET_ENV_KEYS:
    os.environ[_key] = ""

# --- 2. Keep app state out of the repo --------------------------------------
# Without this the suite appends its own hits to the checked-out
# visitor_analytics.json, which then shows up in `git status` and, worse, in
# the next hourly rollup a developer's local run happens to send.
_TMP_STATE = tempfile.mkdtemp(prefix="boilerplate-tests-")
os.environ["TRAFFIC_ANALYTICS_FILE"] = os.path.join(_TMP_STATE, "visitor_analytics.json")
# Same reason for the control board's override store — and pointing it at a
# tmp path also keeps the import-time [visibility] boot warning quiet.
os.environ["PAGE_VISIBILITY_FILE"] = os.path.join(_TMP_STATE, "page_visibility.json")
# Behind Cloudflare in production; in tests an outbound ip-api.com lookup per
# hit would make the suite depend on a third party being up.
os.environ["ANALYTICS_GEO_LOOKUP"] = "0"
# The base-URL guard and the reporter both key off these; keep them inert.
os.environ.setdefault("APP_ENV", "test")

BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)
CRAWLER_UA = "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)"

# What a real browser sends. `/<page>/llms.txt` negotiates on this header —
# not on the User-Agent — so it is what separates "a person opened the URL"
# from "an agent fetched it".
BROWSER_ACCEPT = "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"

# The body dash-improve-my-llms serves when a page has no prose registered.
# Its presence on any page is the failure this whole network cares most about.
STUB_MARKER = "This page contains interactive content that requires JavaScript"


def backend() -> str:
    """Whichever backend the app will actually boot on.

    Not `os.environ["DASH_BACKEND"]` directly: lib/backend.py calls
    `load_dotenv()`, so a local .env can select a backend the bare environment
    knows nothing about. Reading the env here instead would hand out a
    Werkzeug test client for a FastAPI app, and every test would fail on the
    client rather than on the code.
    """
    from lib.backend import resolve_backend

    return resolve_backend()


@pytest.fixture(scope="session")
def app_module():
    """Import run.py as a module, from the repo root.

    run.py opens 'templates/index.html' by relative path and pages/markdown.py
    globs 'docs/**/*.md', so the process CWD has to be the repo root regardless
    of where pytest was invoked from.
    """
    os.chdir(REPO_ROOT)
    spec = importlib.util.spec_from_file_location("runmod", REPO_ROOT / "run.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["runmod"] = module
    try:
        spec.loader.exec_module(module)
    except SystemExit:  # pragma: no cover - run.py doesn't call sys.exit today
        pass
    return module


@pytest.fixture(scope="session")
def app(app_module):
    return app_module.app


class Response:
    __slots__ = ("status", "text", "headers")

    def __init__(self, status: int, text: str, headers=None) -> None:
        self.status = status
        self.text = text
        # Headers matter from 2.2.0 on: `/<page>/llms.txt` content-negotiates,
        # so the *type* of the response is part of the contract and `Vary` is
        # what stops a CDN serving cached HTML to the next agent.
        #
        # Keys are lowercased because the three backends disagree on casing —
        # Werkzeug hands back `Content-Type`, httpx `content-type`. A plain
        # `headers.get("Content-Type")` therefore passes on Flask and fails on
        # FastAPI and Quart, which reads like a backend bug and isn't one.
        self.headers = {k.lower(): v for k, v in (headers or {}).items()}

    @property
    def ok(self) -> bool:
        return self.status == 200

    def header(self, name: str, default: str = "") -> str:
        return self.headers.get(name.lower(), default)

    @property
    def content_type(self) -> str:
        return self.header("Content-Type")

    def __repr__(self) -> str:  # pragma: no cover - assertion output only
        return f"<Response {self.status} {self.content_type} {len(self.text)}b>"


class Client:
    """One synchronous `.get()` across all three backends.

    Quart's test client is async all the way down — both the request and
    `get_data()` return coroutines — so it gets driven from a loop owned by
    the fixture rather than being awaited by every test.
    """

    def __init__(self, raw, kind: str, loop=None) -> None:
        self._raw = raw
        self._kind = kind
        self._loop = loop

    def get(self, path: str, user_agent: str = BROWSER_UA, accept: str = None) -> Response:
        return self.open(path, "GET", user_agent=user_agent, accept=accept)

    def head(self, path: str, user_agent: str = BROWSER_UA, accept: str = None) -> Response:
        """The same request as `.get()`, by the method HTTP pairs with it.

        Its own method rather than a flag because what it pins is a backend
        difference: Werkzeug derives a HEAD rule from every GET one, FastAPI's
        ``APIRoute`` does not, and that is where it stops being invisible.
        """
        return self.open(path, "HEAD", user_agent=user_agent, accept=accept)

    def open(self, path: str, method: str = "GET", user_agent: str = BROWSER_UA,
             accept: str = None) -> Response:
        headers = {"User-Agent": user_agent}
        if accept is not None:
            headers["Accept"] = accept

        if self._kind == "werkzeug":
            r = self._raw.open(path, method=method, headers=headers)
            # errors="replace", not `as_text=True`: the latter decodes strictly
            # and raises UnicodeDecodeError on any binary response, so a test
            # that merely checks a favicon or a manifest icon RESOLVES would
            # blow up on the PNG's first byte. httpx (the FastAPI branch) is
            # already lenient; this matches it.
            return Response(r.status_code, r.get_data().decode("utf-8", "replace"),
                            dict(r.headers))

        if self._kind == "quart":
            async def fetch():
                r = await self._raw.open(path, method=method, headers=headers)
                # Same lenient decode as the werkzeug branch above, and for the
                # same reason — this branch was simply missed when that one was
                # fixed. Quart's `get_data(as_text=True)` decodes strictly, so
                # any test that merely checks a PNG RESOLVES died on the file's
                # first non-UTF-8 byte. It went unnoticed because the tests that
                # fetch binary assets live in tests/test_social_card.py, which
                # was untracked and therefore never ran in CI.
                body = (await r.get_data()).decode("utf-8", "replace")
                return r.status_code, body, dict(r.headers)

            return Response(*self._loop.run_until_complete(fetch()))

        r = self._raw.request(method, path, headers=headers)
        return Response(r.status_code, r.text, dict(r.headers))


@pytest.fixture(scope="session")
def client(app):
    """A test client for whichever backend is under test.

    FastAPI/Quart need the ASGI lifespan to have run: Dash registers its page
    catch-all from the startup event, so a client used outside the lifespan
    context 404s every non-root URL for reasons that have nothing to do with
    the code under test.
    """
    kind = backend()
    if kind == "flask":
        yield Client(app.server.test_client(), "werkzeug")
    elif kind == "quart":
        import asyncio

        loop = asyncio.new_event_loop()
        try:
            yield Client(app.server.test_client(), "quart", loop=loop)
        finally:
            loop.close()
    elif kind == "fastapi":
        from starlette.testclient import TestClient

        with TestClient(app.server) as raw:
            yield Client(raw, "httpx")
    else:  # pragma: no cover - resolve_backend() rejects anything else
        raise RuntimeError(f"unsupported DASH_BACKEND={kind!r}")


@pytest.fixture(scope="session")
def tmp_state_dir():
    """Where the app's ledger and lease files live for this run."""
    return _TMP_STATE


@pytest.fixture(scope="session")
def pages(app_module):
    """Every crawlable page as (path, name, entry), sorted by path.

    /admin/* is excluded on purpose: the control board fails CLOSED to
    anonymous renders (its crawler body is deliberately empty), so the
    prose-substance sweeps would flag exactly the behavior we want.
    tests/test_control_board.py owns that page's assertions.
    """
    import dash

    return sorted(
        ((entry["path"], entry.get("name", ""), entry)
         for entry in dash.page_registry.values()
         if not entry["path"].startswith("/admin/")),
        key=lambda item: item[0],
    )


@pytest.fixture(scope="session")
def page_paths(pages):
    return [path for path, _name, _entry in pages]


def main_body(html: str) -> str:
    """The prerendered <main> block, or '' when the document has none."""
    if "<main>" not in html:
        return ""
    return html.split("<main>", 1)[1].split("</main>", 1)[0]
