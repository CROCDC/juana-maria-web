"""Data access for crew-program applications (CONVENTIONS §5)."""

from __future__ import annotations

from app.factory import db
from app.models import CrewApplication


class CrewApplicationRepository:
    @staticmethod
    def create(
        full_name: str,
        email: str,
        whatsapp: str,
        is_adult: bool = False,
        instagram: str | None = None,
        preferred_date: str | None = None,
        preferred_route: str | None = None,
        message: str | None = None,
    ) -> CrewApplication:
        application = CrewApplication(
            full_name=full_name,
            email=email,
            whatsapp=whatsapp,
            is_adult=is_adult,
            instagram=instagram or None,
            preferred_date=preferred_date or None,
            preferred_route=preferred_route or None,
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
