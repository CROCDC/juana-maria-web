"""The content the public sees, as a build artifact instead of a database query.

Every HTML render used to query Postgres — sitecopy's overrides plus the topic
visibility map — and on a scale-to-zero database each query buys another five minutes
of billed compute. With crawlers hitting the site around the clock it never slept, and
on 2026-09-21 Neon's quota ran out and suspended it. CDN caching was the intended fix
and Vercel declines to store this function's responses at all (docs/deploy/MONITORING.md).

So the public read path stops going over the network. `flask snapshot build` reads the
database once at deploy time and writes `app/content/snapshot.json` into the bundle,
next to `image_manifest.json`, which ships the same way and for the same reason. A page
view then costs no query and no quota of any kind.

Postgres stays the single source of truth. The snapshot is derived and disposable:
there is no runtime writer and nothing to reconcile, and a build either regenerates it
correctly or fails. If the file is missing the readers fall back to the database, so
this is an optimization and never a dependency.
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any

log = logging.getLogger(__name__)

PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "content", "snapshot.json")

# Bumped when the shape changes, so a deploy carrying an old snapshot is ignored rather
# than half-read. The fallback covers the gap until the next build.
VERSION = 1


def build(store: Any, visibility: dict[str, bool]) -> dict[str, Any]:
    """The snapshot, from the live database. Only PUBLISHED values: a draft belongs to
    the admin who staged it and must never reach a public render."""
    from datetime import datetime, timezone

    texts = {
        key: published
        for key, (published, _draft) in store.as_map().items()
        if published is not None
    }
    return {
        "version": VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "texts": texts,
        "topic_visibility": visibility,
    }


def write(data: dict[str, Any]) -> str:
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=1, sort_keys=True)
    return PATH


def load() -> dict[str, Any] | None:
    """The bundled snapshot, or None when there is not a usable one.

    Read once at import. A function instance's filesystem is read-only and fixed for
    the life of the deployment, so re-reading it per request would buy nothing.
    """
    try:
        with open(PATH, encoding="utf-8") as fh:
            data: dict[str, Any] = json.load(fh)
    except FileNotFoundError:
        log.info("no content snapshot bundled; public reads will use the database")
        return None
    except (OSError, ValueError) as exc:
        log.warning("content snapshot unreadable (%s); falling back to the database", exc)
        return None

    if data.get("version") != VERSION:
        log.warning(
            "content snapshot is version %s, this build expects %s; ignoring it",
            data.get("version"),
            VERSION,
        )
        return None
    return data


# Loaded once and remembered, including the "there isn't one" answer: a function
# instance's filesystem is fixed for the life of the deployment, so a second read
# could only ever return the same thing.
_UNREAD = object()
_cached: Any = _UNREAD


def current() -> dict[str, Any] | None:
    global _cached
    if _cached is _UNREAD:
        _cached = load()
    return _cached  # type: ignore[no-any-return]


def texts() -> dict[str, str] | None:
    data = current()
    return None if data is None else data.get("texts", {})


def topic_visibility() -> dict[str, bool] | None:
    data = current()
    return None if data is None else data.get("topic_visibility", {})


def reset_cache() -> None:
    """For tests, which build several apps against different snapshots in one process."""
    global _cached
    _cached = _UNREAD
