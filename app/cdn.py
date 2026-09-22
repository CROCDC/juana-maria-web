"""Purging the CDN's copy of the site, so a long cache TTL and fresh content can both hold.

The CDN is what keeps Neon's bill down: every HTML render queries Postgres, and every
query buys another five minutes of awake compute, so the lever that matters is how
rarely the function renders at all (docs/deploy/MONITORING.md). A long `s-maxage` is
therefore worth a lot — and would make the content editor useless, because an edit
would take that long to reach a visitor. Purging on write is what buys both.

Invalidate, not delete: it marks the entries stale, so the next visitor is served the
stale copy instantly while the refresh happens behind them. Deleting would send every
concurrent visitor to the origin at once.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

INVALIDATE_ENDPOINT = "https://api.vercel.com/v1/edge-cache/invalidate-by-tags"

# Every public page carries this tag, so one call invalidates the whole site. Per-page
# tags would be a false economy: the nav on every page changes when a topic is toggled.
SITE_TAG = "site-html"

# The admin is waiting on the response this runs inside.
_TIMEOUT_SECONDS = 5


def invalidate_site_cache() -> bool:
    """Mark every cached public page stale. Returns whether the call was made.

    Never raises: a failed purge means a visitor sees the previous copy until the TTL
    runs out, which is not worth failing an admin's save over.
    """
    token = os.environ.get("VERCEL_PURGE_TOKEN")
    project = os.environ.get("VERCEL_PROJECT_ID")
    if not (token and project):
        log.info("CDN purge skipped (VERCEL_PURGE_TOKEN/VERCEL_PROJECT_ID unset)")
        return False

    url = f"{INVALIDATE_ENDPOINT}?projectIdOrName={project}"
    team = os.environ.get("VERCEL_TEAM_ID")
    if team:
        url += f"&teamId={team}"

    # A preview deployment must not invalidate production's cache.
    target = "preview" if os.environ.get("VERCEL_ENV") == "preview" else "production"

    req = urllib.request.Request(
        url,
        data=json.dumps({"tags": [SITE_TAG], "target": target}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
            log.info("CDN purge %s -> %s", target, resp.status)
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.warning("CDN purge failed: %s", exc)
        return False
