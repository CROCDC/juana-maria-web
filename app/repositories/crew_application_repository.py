"""Data access for crew-program applications (CONVENTIONS §5)."""

from __future__ import annotations

from app.factory import db
from app.models import CrewApplication


class CrewApplicationRepository:
    @staticmethod
    def create(
        full_name: str,
        email: str,
        phone: str | None = None,
        experience: str | None = None,
        message: str | None = None,
    ) -> CrewApplication:
        application = CrewApplication(
            full_name=full_name,
            email=email,
            phone=phone or None,
            experience=experience or None,
            message=message or None,
        )
        db.session.add(application)
        db.session.commit()
        return application

    @staticmethod
    def get_all() -> list[CrewApplication]:
        return (
            CrewApplication.query.order_by(CrewApplication.created_at.desc()).all()
        )
