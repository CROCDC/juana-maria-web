"""Data access layer.

Convention (CONVENTIONS.md §5):
- One module per entity, e.g. ``contact_repository.py``.
- Each repository is a class with static methods: ``get_all``, ``get_by_id``,
  ``save``, ``create_xxx``, etc., all fully type-hinted (single entity ->
  ``Optional[Model]``, collection -> ``list[Model]``).
- Repositories own all queries and ``db.session`` access. Routes call
  repositories, never the ORM directly.
- Import models from ``app.models`` and ``db`` from ``app.factory``. Do not
  import Flask ``request`` or ``app`` here; the route layer passes plain data in.

Example:

    from typing import Optional

    from app.factory import db
    from app.models import ContactMessage


    class ContactRepository:
        @staticmethod
        def save(name: str, email: str, message: str) -> ContactMessage:
            entity = ContactMessage(name=name, email=email, message=message)
            db.session.add(entity)
            db.session.commit()
            return entity
"""
