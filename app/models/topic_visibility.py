"""Per-topic published state — the only mutable, DB-owned part of the topics.

Topic *definitions* live in ``app/content/topics.py``; this table stores just
whether each toggleable topic is currently published. One row per topic slug,
flipped from the admin panel.
"""

from __future__ import annotations

from typing import Any

from app.factory import db


class TopicVisibility(db.Model):  # type: ignore[name-defined,misc]
    __tablename__ = "topic_visibility"

    id = db.Column(db.Integer, primary_key=True)
    # Matches Topic.slug in app/content/topics.py (the join key).
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    enabled = db.Column(db.Boolean, nullable=False, default=False)

    def to_dict(self) -> dict[str, Any]:
        return {"slug": self.slug, "enabled": self.enabled}
