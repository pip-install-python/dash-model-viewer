"""dimll 2.6.0's SEO honesty features, pinned from the app's side.

Two contracts land with the 2.6.0 floor:

1. **Icon discovery agrees with the declaration.** This app still declares
   `configure_seo(icons=[...])` explicitly (declared wins), but the fleet's
   satellites will increasingly rely on discovery alone — so the reference
   host proves the two produce the SAME set. Set-equality, not order: the
   release notes are explicit that discovery orders differently
   (.ico first, biggest square descending, apple-touch last) and that
   order-inequality is not a failure.

2. **The sitemap tells the truth or says nothing.** `<lastmod>` is emitted
   verbatim from frontmatter `lastmod:` and omitted when unset. No date in
   the sitemap may exist that no page declared — the invented daily "today"
   is the exact lie 2.6.0 exists to end.
"""

from __future__ import annotations

import re
from pathlib import Path


def _normalize(entries):
    """(rel, href, sizes) triples from the package's mixed icon shapes."""
    out = set()
    for e in entries:
        if isinstance(e, str):
            out.add(("icon", e, None))
        else:
            out.add((e.get("rel", "icon"), e["href"], e.get("sizes")))
    return out


def test_discovery_agrees_with_the_declared_icons(app):
    from dash_improve_my_llms.seo import _config, discover_icons

    declared = _normalize(_config.icons or [])
    discovered = _normalize(discover_icons(app))

    assert declared, "configure_seo(icons=) is no longer declared in run.py?"
    assert discovered, "discovery found nothing in assets/ — pattern drift?"
    assert declared == discovered, (
        "Declared and discovered icon sets diverged.\n"
        f"declared only:   {sorted(declared - discovered)}\n"
        f"discovered only: {sorted(discovered - declared)}\n"
        "If a favicon file was added/renamed, update run.py's icons list — "
        "or if discovery's patterns changed upstream, this is the canary."
    )


def _declared_lastmods() -> set[str]:
    dates = set()
    for md in Path("docs").glob("**/*.md"):
        head = md.read_text().split("---")[1] if md.read_text().startswith("---") else ""
        m = re.search(r"^lastmod:\s*(\d{4}-\d{2}-\d{2})\s*$", head, re.MULTILINE)
        if m:
            dates.add(m.group(1))
    return dates


def test_sitemap_lastmod_is_verbatim_or_absent(client):
    sitemap = client.get("/sitemap.xml").text
    emitted = re.findall(r"<lastmod>([^<]+)</lastmod>", sitemap)
    declared = _declared_lastmods()

    assert emitted, (
        "No <lastmod> anywhere — the frontmatter stamps were removed? "
        "Truth-or-silence allows silence per page, but the docs set "
        "deliberately declares real dates."
    )
    undeclared = [d for d in emitted if d not in declared]
    assert not undeclared, (
        f"Sitemap emits dates nobody declared: {undeclared} — an invented "
        "date is the lie that gets the whole sitemap discarded."
    )

    # The home page declares no lastmod; its <url> entry must carry none.
    home_block = re.search(
        r"<url>\s*<loc>[^<]*?://[^/<]+/</loc>.*?</url>", sitemap, re.DOTALL
    )
    assert home_block and "<lastmod>" not in home_block.group(0), (
        "The home page's sitemap entry carries a lastmod it never declared."
    )
