from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.factory import db


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class CrewApplication(db.Model):  # type: ignore[name-defined,misc]
    __tablename__ = "crew_applications"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(160), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    whatsapp = db.Column(db.String(40), nullable=False)
    instagram = db.Column(db.String(80), nullable=True)
    is_adult = db.Column(db.Boolean, nullable=False, default=False)
    preferred_date = db.Column(db.String(120), nullable=True)
    preferred_route = db.Column(db.String(80), nullable=True)
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "whatsapp": self.whatsapp,
            "instagram": self.instagram,
            "is_adult": self.is_adult,
            "preferred_date": self.preferred_date,
            "preferred_route": self.preferred_route,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
