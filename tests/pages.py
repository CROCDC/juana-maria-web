from __future__ import annotations

PUBLIC_PAGES: list[str] = [
    "/",
    "/crew-program",
]

VIEWPORTS: list[tuple[str, int, int]] = [
    ("mobile-375", 375, 667),
    ("mobile-414", 414, 896),
    ("tablet-768", 768, 1024),
    ("tablet-1024", 1024, 768),
    ("desktop-1280", 1280, 720),
]


def page_slug(path: str) -> str:
    return path.strip("/").replace("/", "_") or "home"
