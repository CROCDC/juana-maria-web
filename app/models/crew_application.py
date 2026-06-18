"""A crew-program application submitted from the public intake form.

Persisted so submissions aren't lost; a future admin view can list them. The
field set is intentionally small and may be adjusted when the client confirms
the exact data they want to collect (see topics/crew-program.html).
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
    phone = db.Column(db.String(40), nullable=True)
    experience = db.Column(db.String(40), nullable=True)
    message = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=_utcnow)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "full_name": self.full_name,
            "email": self.email,
            "phone": self.phone,
            "experience": self.experience,
            "message": self.message,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }
