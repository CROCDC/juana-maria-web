"""SQLAlchemy models.

Convention (CONVENTIONS.md §4):
- One file per domain entity, e.g. ``contact_message.py``.
- Each model imports ``db`` from ``app.factory`` and subclasses ``db.Model``.
- Re-export every model here so the rest of the app can do
  ``from app.models import ContactMessage``.
- No queries or persistence logic in models — that belongs in repositories (§5).

For Flask-Migrate autogenerate to detect a model it must be imported here, since
this package is imported inside the factory's app context.

Example:

    from app.models.contact_message import ContactMessage

    __all__ = ["ContactMessage"]
"""
