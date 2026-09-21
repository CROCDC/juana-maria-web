from __future__ import annotations

import logging
from typing import NamedTuple

from flask import g, has_app_context

from app.content.topics import DEFAULT_ENABLED
from app.factory import db
from app.models import TopicVisibility

log = logging.getLogger(__name__)

# Last map read successfully, so a database outage degrades the public site instead of
# taking it down. On 2026-09-21 Neon's quota suspended the compute and every topic page
# 500'd while the home page stayed up — its read was the only one with a net, and even
# that one emptied the nav. Per process, so a cold start during an outage falls through
# to DEFAULT_ENABLED; it is a cache for staying up, never a source of truth.
_last_known: dict[str, bool] | None = None


class Visibility(NamedTuple):
    """`authoritative` is False when `state` is a guess made while Postgres was down.

    Callers that turn a False into a 404 need it: claiming "not found" for a page that
    is probably published invites Google to drop it, so an unauthoritative miss is a
    503 instead.
    """

    state: dict[str, bool]
    authoritative: bool


class TopicVisibilityRepository:
    @staticmethod
    def get_state_map() -> dict[str, bool]:
        """The stored map. Raises if the database is unreachable — callers that must
        not lie (the admin panel, any write) need to hear about it."""
        global _last_known
        state = {row.slug: row.enabled for row in TopicVisibility.query.all()}
        _last_known = state
        return state

    @staticmethod
    def published_state() -> Visibility:
        """What the public is shown, answered even when Postgres is down.

        Falls back to the last good read, then to the defaults the site ships with.
        The trade-off is deliberate: a topic that was switched off can reappear during
        an outage, which beats 500ing every page on the site.
        """
        try:
            return Visibility(TopicVisibilityRepository.get_state_map(), True)
        except Exception as exc:  # noqa: BLE001 — staying up is the whole point
            # Flagged so the response never reaches the CDN: a degraded page cached for
            # an hour would outlive the outage that produced it.
            if has_app_context():
                g.visibility_degraded = True
            if _last_known is not None:
                log.warning("topic visibility from cache (%s)", exc)
                return Visibility(_last_known, False)
            log.warning("topic visibility from defaults (%s)", exc)
            return Visibility(dict(DEFAULT_ENABLED), False)

    @staticmethod
    def set_enabled(slug: str, enabled: bool) -> None:
        global _last_known
        row = TopicVisibility.query.filter_by(slug=slug).first()
        if row is None:
            row = TopicVisibility(slug=slug, enabled=enabled)
            db.session.add(row)
        else:
            row.enabled = enabled
        db.session.commit()
        # Or the cache would serve the pre-edit map for the rest of the process' life.
        if _last_known is not None:
            _last_known = {**_last_known, slug: enabled}

    @staticmethod
    def ensure_seeded(defaults: dict[str, bool]) -> None:
        existing = {row.slug for row in TopicVisibility.query.all()}
        missing = [slug for slug in defaults if slug not in existing]
        if not missing:
            return
        for slug in missing:
            db.session.add(TopicVisibility(slug=slug, enabled=defaults[slug]))
        db.session.commit()
