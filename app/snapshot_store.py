"""A sitecopy `TextStore` that answers public renders from the snapshot.

`as_map()` is the only method on the hot path — sitecopy's resolver calls it once per
request and nothing else touches the database on a public render — so it is the only
one this intercepts. Everything else (drafts, preview, publish, the version history)
belongs to the admin and goes straight to the real store, which keeps Postgres as the
one place a write can land.

Anonymous requests never see a draft anyway: `_admin_flag` in sitecopy requires both
`?preview=1` and a session. Returning `(published, None)` here is therefore not a
simplification, it is the same answer the resolver would have computed.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from flask import has_request_context
from sitecopy import TextStore

log = logging.getLogger(__name__)


class SnapshotTextStore(TextStore):  # type: ignore[misc]
    def __init__(
        self,
        inner: TextStore,
        texts: Callable[[], dict[str, str] | None],
        is_admin: Callable[[], bool],
    ) -> None:
        self._inner = inner
        self._texts = texts
        self._is_admin = is_admin

    def as_map(self) -> dict[str, tuple[str | None, str | None]]:
        # `is_admin` reads the session, which needs a request; sitecopy's own cache
        # falls back to the app context, so this can run without one.
        admin = has_request_context() and self._is_admin()
        # The admin is shown the truth, always: they are about to edit it.
        if not admin:
            texts = self._texts()
            if texts is not None:
                return {key: (value, None) for key, value in texts.items()}
        return self._inner.as_map()

    # --- everything below is the admin's, and belongs to the database ---------

    def previous_map(self) -> dict[str, str]:
        return self._inner.previous_map()

    def draft_keys(self) -> list[str]:
        return self._inner.draft_keys()

    def get(self, key: str) -> Any:
        return self._inner.get(key)

    def set_draft(self, key: str, value: str | None) -> None:
        self._inner.set_draft(key, value)

    def set_published(self, key: str, value: str | None) -> None:
        self._inner.set_published(key, value)

    def publish(self, keys: list[str], defaults: dict[str, str]) -> int:
        return self._inner.publish(keys, defaults)

    def discard_drafts(self, keys: list[str]) -> int:
        return self._inner.discard_drafts(keys)

    def delete(self, key: str) -> bool:
        deleted: bool = self._inner.delete(key)
        return deleted

    def commit(self) -> None:
        self._inner.commit()

    def rollback(self) -> None:
        self._inner.rollback()

    def ensure_schema(self) -> None:
        self._inner.ensure_schema()
