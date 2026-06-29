"""A crew-program application submitted from the public intake form.

Persisted so submissions aren't lost and listed in the admin panel. The fields
mirror the client's intake questions: how to reach the applicant (email,
WhatsApp, Instagram), whether they're of age, and when/where they'd like to sail
(see topics/crew-program.html).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.factory import db


def _utcnow() -> datetime:
    # Timezone-aware UTC (datetime.utcnow() is deprecated in 3.12).
    return datetime.now(timezone.utc)


class CrewApplication(db.Model):  # type: ignore[name-defined,misc]
    __tablename__ = "crew_applications"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(160), nullable=False)
    email = db.Column(db.String(254), nullable=False)
    # WhatsApp is the primary channel back to the applicant, so it's required.
    whatsapp = db.Column(db.String(40), nullable=False)
    instagram = db.Column(db.String(80), nullable=True)
    is_adult = db.Column(db.Boolean, nullable=False, default=False)
    # When they'd like to sail: free text, since plans are usually approximate
    # ("un sábado de noviembre") rather than an exact calendar date.
    preferred_date = db.Column(db.String(120), nullable=True)
    # Which of the rumbos they'd prefer; stores the rumbo key, empty if none.
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
