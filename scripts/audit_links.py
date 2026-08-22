#!/usr/bin/env python3
"""Audit every link in every ``llms.txt`` document.

    python scripts/audit_links.py              # boot the app, check everything
    python scripts/audit_links.py --no-network # skip third-party HTTP checks

A page's ``llms.txt`` is the copy an agent is handed, and a dead link in it is
worse than a dead link on a page: the agent has no navigation to fall back on
and no way to tell a typo from a host that is down. This walks every document,
extracts every link, resolves the internal ones against the running app, and
classifies the rest.

Link classes, because they fail for different reasons and want different fixes:

``internal``    A path on this host. Resolved in-process — a failure here is a
                genuine broken link.
``self-host``   An absolute URL to this app's own ``BASE_URL``. Correct in
                production, unreachable in local development. Reported
                separately so "not deployed yet" never hides a real 404.
``network``     Another host in the 2plot network. Expected to fail until the
                rollout finishes.
``external``    Third-party. Checked over the network unless --no-network.
``anchor``      A ``#fragment``. Checked against the heading ids in the same
                document.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import sys
import ssl
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List, Tuple
from urllib.parse import urlparse, urlsplit

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

# [label](target) and bare URLs. Markdown link targets are taken first so the
# bare-URL pass does not also match the URL inside a link.
MD_LINK = re.compile(r"\[([^\]]*)\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
# Trailing markdown punctuation is not part of the URL: `**https://x**`,
# `` `https://x` `` and "see https://x." all otherwise capture a character
# that turns a live link into a 404 in the report.
BARE_URL = re.compile(r"(?<![(<\"])\bhttps?://[^\s)<>\"'\]]+")
TRAILING_JUNK = re.compile(r"[*`.,;:!?\'\"]+$")
HEADING = re.compile(r"^#{1,6}\s+(.*)$", re.M)
CODE_FENCE = re.compile(r"^```.*?^```", re.M | re.S)
# A URL inside backticks is text, not a link — the renderer emits <code>, not
# <a>. Reporting it as broken tells people to "fix" something no reader can
# click, which is how an audit trains you to ignore it.
INLINE_CODE = re.compile(r"`[^`\n]*`")


def slug(text: str) -> str:
    text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[`*_~]", "", text)
    return "-".join(text.lower().split())


def boot():
    spec = importlib.util.spec_from_file_location("runmod", REPO_ROOT / "run.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules["runmod"] = module
    try:
        spec.loader.exec_module(module)
    except SystemExit:  # pragma: no cover
        pass
    return module


def _ssl_context() -> ssl.SSLContext:
    """Verify certificates properly.

    A bare `urlopen` uses whatever CA store the interpreter was built against,
    which on some macOS Python builds is empty — every HTTPS link then reports
    as unreachable and the audit is worse than useless, because it produces a
    long list of confident false positives.
    """
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except ImportError:  # pragma: no cover
        return ssl.create_default_context()


SSL_CONTEXT = _ssl_context()

# Every UA this script sends carries the network's internal-traffic token: a
# link audit sweeps every peer in the directory, and a sweep must not register
# as a visitor (or as a "bot") in another satellite's ledger. See
# lib/constants.INTERNAL_UA. Third-party hosts simply ignore it.
try:
    from lib.constants import INTERNAL_UA as _INTERNAL_UA
except Exception:  # pragma: no cover — running outside a checkout
    _INTERNAL_UA = "2plot-internal/1.0 (+https://2plot.ai/docs/satellite-analytics)"

AUDIT_UA = f"Mozilla/5.0 (compatible; link-audit/1.0) {_INTERNAL_UA}"


def check_external(url: str, cache: Dict[str, int], _retrying: bool = False) -> int:
    if url in cache:
        return cache[url]
    request = urllib.request.Request(
        url,
        headers={"User-Agent": AUDIT_UA},
        method="HEAD",
    )
    try:
        with urllib.request.urlopen(request, timeout=15, context=SSL_CONTEXT) as response:
            status = response.status
    except urllib.error.HTTPError as exc:
        # Plenty of hosts refuse HEAD but serve GET.
        if exc.code in (403, 405, 501):
            try:
                get = urllib.request.Request(url, headers={"User-Agent": AUDIT_UA})
                with urllib.request.urlopen(get, timeout=15, context=SSL_CONTEXT) as response:
                    status = response.status
            except Exception:
                status = exc.code
        else:
            status = exc.code
    except Exception:
        status = 0

    # One retry on a transport failure. Forums and CDNs rate-limit, and a
    # single timeout reported as "broken" is a false positive — which is how
    # an audit trains its reader to stop believing it.
    if status == 0 and not _retrying:
        return check_external(url, cache, _retrying=True)

    cache[url] = status
    return status


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-network", action="store_true")
    args = parser.parse_args()

    module = boot()
    client = module.app.server.test_client()

    import dash

    from lib import network_directory as nd
    from lib.constants import BASE_URL

    base_host = urlparse(BASE_URL).netloc
    network_hosts = {urlparse(p["url"]).netloc for p in nd.PEERS}

    docs: List[Tuple[str, str]] = [("/", "/llms.txt")]
    for entry in sorted(dash.page_registry.values(), key=lambda e: e["path"]):
        if entry["path"] != "/":
            docs.append((entry["path"], f"{entry['path'].rstrip('/')}/llms.txt"))

    findings: Dict[str, List[Tuple[str, str, str]]] = {
        "internal": [], "anchor": [], "self-host": [], "network": [], "external": [],
        "unpushed": [],
    }

    # Links into this repo's own GitHub tree 404 until the branch is pushed.
    # That is a publishing state, not a broken link, and conflating the two
    # means every newly added file shows up as a defect until release.
    own_tree = re.compile(
        r"^https://github\.com/[^/]+/Dash-Documentation-Boilerplate/blob/[^/]+/(.+)$"
    )
    external_cache: Dict[str, int] = {}
    total = 0

    for page, doc_url in docs:
        response = client.get(doc_url)
        if response.status_code != 200:
            findings["internal"].append((doc_url, doc_url, f"document itself {response.status_code}"))
            continue
        body = response.get_data(as_text=True)
        prose = INLINE_CODE.sub("", CODE_FENCE.sub("", body))  # code is not a link
        ids = {slug(h) for h in HEADING.findall(prose)}

        targets = [t for _label, t in MD_LINK.findall(prose)]
        targets += [TRAILING_JUNK.sub("", u) for u in BARE_URL.findall(prose)]

        for target in dict.fromkeys(targets):
            total += 1
            parsed = urlsplit(target)

            if target.startswith("#"):
                if target[1:] not in ids:
                    findings["anchor"].append((page, target, "no such heading in this document"))
                continue

            if parsed.scheme in ("mailto", "tel"):
                continue

            if not parsed.scheme:  # relative or root-relative path
                path = parsed.path or "/"
                if not path.startswith("/"):
                    findings["internal"].append((page, target, "relative path, ambiguous in llms.txt"))
                    continue
                probe = client.get(path)
                if probe.status_code != 200:
                    findings["internal"].append((page, target, f"HTTP {probe.status_code}"))
                continue

            host = parsed.netloc
            if host == base_host:
                probe = client.get(parsed.path or "/")
                status = "resolves once deployed" if probe.status_code == 200 else f"HTTP {probe.status_code} even locally"
                findings["self-host"].append((page, target, status))
            elif host in network_hosts:
                findings["network"].append((page, target, "network host, not deployed yet"))
            else:
                if args.no_network:
                    continue
                status = check_external(target, external_cache)
                if status == 200:
                    continue
                own = own_tree.match(target)
                if own and (REPO_ROOT / own.group(1)).exists():
                    findings["unpushed"].append(
                        (page, target, f"{own.group(1)} exists locally; 404 until pushed")
                    )
                else:
                    findings["external"].append(
                        (page, target, f"HTTP {status}" if status else "unreachable")
                    )

    print(f"Audited {len(docs)} documents, {total} links\n")

    print(f"BROKEN — internal ({len(findings['internal'])})")
    for page, target, why in findings["internal"]:
        print(f"    {page:<28} {target:<58} {why}")

    print(f"\nBROKEN — external ({len(findings['external'])})")
    for page, target, why in findings["external"]:
        print(f"    {page:<28} {target:<58} {why}")

    print(f"\nBROKEN — anchors ({len(findings['anchor'])})")
    for page, target, why in findings["anchor"]:
        print(f"    {page:<28} {target:<58} {why}")

    bad_self = [f for f in findings["self-host"] if "even locally" in f[2]]
    print(f"\nSELF-HOST absolute URLs: {len(findings['self-host'])}"
          f" ({len(bad_self)} broken beyond deployment)")
    for page, target, why in bad_self:
        print(f"    {page:<28} {target:<58} {why}")

    print(f"\nUNPUSHED — this repo's own files ({len(findings['unpushed'])})")
    for page, target, why in findings["unpushed"]:
        print(f"    {page:<28} {why}")

    print(f"\nNETWORK peers (expected, pre-deploy): {len(findings['network'])}")

    broken = len(findings["internal"]) + len(findings["external"]) + len(findings["anchor"]) + len(bad_self)
    print(f"\n{broken} link(s) need a decision")
    return min(broken, 125)


if __name__ == "__main__":
    sys.exit(main())
