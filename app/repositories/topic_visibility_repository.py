"""Data access for per-topic published state (CONVENTIONS §5)."""

from __future__ import annotations

from app.factory import db
from app.models import TopicVisibility


class TopicVisibilityRepository:
    @staticmethod
    def get_state_map() -> dict[str, bool]:
        """Return ``{slug: enabled}`` for every persisted topic."""
        return {row.slug: row.enabled for row in TopicVisibility.query.all()}

    @staticmethod
    def is_enabled(slug: str) -> bool:
        row = TopicVisibility.query.filter_by(slug=slug).first()
        return bool(row and row.enabled)

    @staticmethod
    def set_enabled(slug: str, enabled: bool) -> None:
        row = TopicVisibility.query.filter_by(slug=slug).first()
        if row is None:
            row = TopicVisibility(slug=slug, enabled=enabled)
            db.session.add(row)
        else:
            row.enabled = enabled
        db.session.commit()

    @staticmethod
    def ensure_seeded(defaults: dict[str, bool]) -> None:
        """Insert a row for any topic slug that has none yet.

        Idempotent: existing rows keep whatever state the admin set; only
        brand-new topics get their default published state. Runs at startup.
        """
        existing = {row.slug for row in TopicVisibility.query.all()}
        missing = [slug for slug in defaults if slug not in existing]
        if not missing:
            return
        for slug in missing:
            db.session.add(TopicVisibility(slug=slug, enabled=defaults[slug]))
        db.session.commit()
