"""Uploads backend for the content editor when the site runs on Vercel.

A Vercel Function's filesystem is read-only and thrown away between deploys, so
sitecopy's ``LocalFileStore`` — which writes under the served static folder — has
nowhere to write. Vercel Blob is the durable store; ``FileStore`` is a one-method
interface, so bridging the two is this file.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.error
import urllib.parse
import urllib.request

from sitecopy.media import FileStore, MediaKind

_API_URL = "https://blob.vercel-storage.com"
# Blob's HTTP API is versioned by header, not by URL. 10 is what the current
# official SDKs send; bumping it is a deliberate act, not a default.
_API_VERSION = "10"
_PREFIX = "sitecopy-uploads"
_CACHE_MAX_AGE = "31536000"


class VercelBlobFileStore(FileStore):
    """Store uploaded media in Vercel Blob and return its public CDN URL.

    Names are content-addressed exactly like ``LocalFileStore``'s
    (``sha1(bytes)[:16] + ext``), so re-uploading the same picture is idempotent —
    one blob, one URL, no duplicates piling up in the version history — and a
    client-supplied filename never reaches the store.
    """

    def __init__(self, token: str | None = None, timeout: int = 20) -> None:
        self.token = token if token is not None else os.environ.get("BLOB_READ_WRITE_TOKEN", "")
        self.timeout = timeout

    @property
    def enabled(self) -> bool:
        return bool(self.token)

    def save(self, data: bytes, kind: MediaKind) -> str:
        pathname = f"{_PREFIX}/{hashlib.sha1(data).hexdigest()[:16]}{kind.ext}"
        request = urllib.request.Request(
            f"{_API_URL}/?pathname={urllib.parse.quote(pathname)}",
            data=data,
            method="PUT",
            headers={
                "access": "public",
                "authorization": f"Bearer {self.token}",
                "x-api-version": _API_VERSION,
                "x-content-type": kind.content_type,
                "x-cache-control-max-age": _CACHE_MAX_AGE,
                # The name IS the content hash, so an existing blob under it is
                # byte-for-byte this upload; without this a re-upload 409s.
                "x-allow-overwrite": "1",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                payload = json.load(response)
        except urllib.error.HTTPError as exc:  # surface Blob's own message in the logs
            detail = exc.read().decode("utf-8", "replace")[:500]
            raise RuntimeError(f"Vercel Blob upload failed ({exc.code}): {detail}") from exc
        url = payload.get("url")
        if not url:
            raise RuntimeError(f"Vercel Blob upload returned no url: {payload}")
        return str(url)
