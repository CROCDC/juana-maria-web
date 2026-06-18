"""Shared page list + viewport matrix for the responsive/overflow layers.

Single source of truth so the overflow guard and the responsive test never drift.

Import note: this assumes pytest's DEFAULT import mode with `tests/` NOT a package
(no `__init__.py`) — sibling modules import by bare name (`from pages import ...`).
If your project makes `tests/` a package, switch both imports to `from .pages ...`.
"""

from __future__ import annotations

# Every public (no-auth) path the responsive/overflow layers exercise. The home
# is always public; "/crew-program" is the one topic published by default (see
# DEFAULT_ENABLED in app/content/topics.py), so it's a stable second page. Other
# topics are off by default and 404 until switched on in the admin panel.
PUBLIC_PAGES: list[str] = [
    "/",
    "/crew-program",
]

# (name, width, height): mobile, large mobile, tablet portrait, tablet landscape,
# desktop. The committed screenshots key off these names.
VIEWPORTS: list[tuple[str, int, int]] = [
    ("mobile-375", 375, 667),
    ("mobile-414", 414, 896),
    ("tablet-768", 768, 1024),
    ("tablet-1024", 1024, 768),
    ("desktop-1280", 1280, 720),
]


def page_slug(path: str) -> str:
    """Filesystem-safe screenshot name for a path ('/' -> 'home')."""
    return path.strip("/").replace("/", "_") or "home"
