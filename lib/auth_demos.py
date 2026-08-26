"""Teaser demos for the authentication gate cards.

Each auth-gated docs page can register ONE live example that renders inside
the sign-in card (lib.gate_layouts.sign_in_layout) — an interactive taste of
what's behind the gate, with no code and no surrounding docs.

The modules referenced here are the same ``.. exec::`` example modules the
docs pages use (they expose a module-level ``component``), so they're already
imported — and their callbacks already registered — when pages/markdown.py
parses the docs at startup. Only one layout (gate card OR full docs) renders
per request, so sharing the component instances never duplicates IDs.

The table ships EMPTY in the template: entries are site-specific dotted
paths, so each satellite fills in its own hero example (one entry is plenty —
this is a funnel, not a gallery).

Entries:
    endpoint -> {
        "module":     dotted path of the example module,
        "caption":    short label shown next to the "Live demo" badge,
        "max_height": px cap for the demo viewport inside the card,
        "height":     optional explicit px height — needed by components that
                      size to their container,
    }
"""
from __future__ import annotations

import importlib
import logging

logger = logging.getLogger(__name__)

DEMOS: dict[str, dict] = {
    # This fork's hero, replacing the template's /examples/visualization —
    # an endpoint that is a page in the TEMPLATE and on no fork, so every
    # inheriting site's gate cards rendered demo-less and silent from fork
    # time (batch-1 finding, excalidraw 2026-08-25; tests/test_auth_demos.py
    # is the loud surface now).
    #
    # AR is the headline of this package — it is in SITE_DESCRIPTION — so the
    # highest-intent moment on the site should show a real model, spinnable,
    # with the AR button on it. The module is already imported at boot by the
    # page's own `.. exec::` directive, so build_demo's import_module is a
    # sys.modules hit and registers no callbacks after the app starts serving.
    # Deliberately NOT generative-3d or image-to-3d: one calls a paid model
    # and the other carves geometry at import — neither belongs behind an
    # UNAUTHENTICATED card.
    "/augmented-reality": {
        "module": "docs.augmented-reality.ar_viewer",
        "caption": "Live AR-capable viewer",
        "max_height": 420,
    },
}


def build_demo(path: str):
    """Return the teaser demo block for ``path``, or None.

    Import/attribute failures degrade to the plain (demo-less) card — a broken
    example must never take down the sign-in funnel.
    """
    spec = DEMOS.get(path)
    if spec is None:
        return None
    try:
        module = importlib.import_module(spec["module"])
        component = getattr(module, "component")
    except Exception as e:
        logger.warning("Auth-gate demo %s failed to load (%s) — card renders "
                       "without it", spec.get("module"), e)
        return None

    import dash_mantine_components as dmc
    from dash_iconify import DashIconify

    return dmc.Box(
        [
            dmc.Group(
                [
                    dmc.Badge(
                        "Live demo — try it",
                        variant="light",
                        color="teal",
                        leftSection=DashIconify(icon="tabler:hand-click", width=13),
                    ),
                    dmc.Text(spec.get("caption", ""), size="sm", c="dimmed"),
                ],
                justify="space-between",
                px="md",
                pt="md",
            ),
            dmc.Box(
                component,
                p="md",
                className="auth-gate-demo",
                style={
                    "maxHeight": f"{spec.get('max_height', 420)}px",
                    "overflowY": "auto",
                    "overflowX": "hidden",
                    **({"height": f"{spec['height']}px"} if "height" in spec else {}),
                },
            ),
        ]
    )
