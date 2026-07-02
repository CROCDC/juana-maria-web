from __future__ import annotations

from typing import Any

from app.factory import db


class TopicVisibility(db.Model):  # type: ignore[name-defined,misc]
    __tablename__ = "topic_visibility"

    id = db.Column(db.Integer, primary_key=True)
    slug = db.Column(db.String(64), unique=True, nullable=False, index=True)
    enabled = db.Column(db.Boolean, nullable=False, default=False)

    def to_dict(self) -> dict[str, Any]:
        return {"slug": self.slug, "enabled": self.enabled}
