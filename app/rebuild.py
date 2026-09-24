"""Asking the deploy pipeline to rebuild, because the public content ships in the bundle.

The snapshot in `app/snapshot.py` is what keeps a page view from touching Postgres, and
it is written at deploy time. So the moment an admin changes what the public should
see, the site needs a new deployment — otherwise the change sits in the database and
nobody outside the admin ever sees it.

This fires the deploy workflow through GitHub's **workflow dispatch**, not
`repository_dispatch`. The two do the same job here and cost very different privileges:
a fine-grained token for `repository_dispatch` needs `Contents: write`, which is the
ability to push code to the repository, while workflow dispatch needs only
`Actions: write` — run workflows, nothing else. This token sits in a web application's
runtime environment, so it gets the smaller of the two.

It is deliberately soft: the write has already been committed to Postgres by the time
this runs, so a failure here means the content is safe but unpublished, and the alert
says exactly that. `gh workflow run vercel.yml` is the manual way through.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

log = logging.getLogger(__name__)

# The admin is waiting on the response this runs inside.
_TIMEOUT_SECONDS = 5

# Only the writes that change what an anonymous visitor is served. A draft save is the
# whole point of having drafts — it must not deploy anything, or an editing session
# becomes fifty deployments.
REBUILD_PATHS = frozenset(
    {
        "/admin/content/publish",  # drafts go live
        "/admin/content/revert",   # a published value rolls back to the previous one
        "/admin/topics",           # a topic is shown or hidden
    }
)


def triggers_rebuild(path: str) -> bool:
    return path.rstrip("/") in REBUILD_PATHS or path in REBUILD_PATHS


def request_rebuild() -> bool:
    """Ask the pipeline for a new deployment. Returns whether the call was made."""
    token = os.environ.get("GITHUB_DISPATCH_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY")
    if not (token and repo):
        log.info("rebuild not requested (GITHUB_DISPATCH_TOKEN/GITHUB_REPOSITORY unset)")
        return False

    workflow = os.environ.get("GITHUB_DEPLOY_WORKFLOW", "vercel.yml")
    ref = os.environ.get("GITHUB_DEPLOY_REF", "main")

    req = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/actions/workflows/{workflow}/dispatches",
        data=json.dumps({"ref": ref}).encode(),
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "velaclasica-rebuild/1",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_TIMEOUT_SECONDS) as resp:
            log.info("rebuild requested: %s", resp.status)
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.warning("rebuild request failed: %s", exc)
        return False
