"""Outbound alert mail, so a production failure reaches a person instead of a log.

Vercel's runtime logs are the only logs this deploy has and they are short-lived
(see docs/deploy/VERCEL.md). On 2026-09-21 Neon's quota suspended the database and
every DB-backed page 500'd for hours with nobody watching — the logs had the whole
story, but nothing carried it out of the platform.

Delivery is Resend's HTTP API, not SMTP: a Vercel Function has a short wall clock and
no outbound SMTP guarantees, and the identical call works from a GitHub runner, which
is where the synthetic checks in `scripts/monitor.py` run.
"""

from __future__ import annotations

import json
import logging
import os
import time
import traceback
import urllib.error
import urllib.request
from typing import Any

from flask import Flask, got_request_exception, request

log = logging.getLogger(__name__)

RESEND_ENDPOINT = "https://api.resend.com/emails"

# Every alert in flight is a request the visitor is waiting on, so the send has to give
# up long before the function's own timeout does.
_SEND_TIMEOUT_SECONDS = 5

# Last send per dedup key. A function instance dies with its container and Vercel runs
# several at once, so this bounds the flood per instance rather than globally — the
# difference between a handful of mails and one per failing request.
_last_sent: dict[str, float] = {}


def _throttle_seconds() -> int:
    try:
        return int(os.environ.get("ALERT_THROTTLE_SECONDS", "900"))
    except ValueError:
        return 900


def _should_send(dedup_key: str | None) -> bool:
    if dedup_key is None:
        return True
    now = time.monotonic()
    previous = _last_sent.get(dedup_key)
    if previous is not None and now - previous < _throttle_seconds():
        return False
    _last_sent[dedup_key] = now
    return True


def send_alert(subject: str, body: str, *, dedup_key: str | None = None) -> bool:
    """Mail one alert. Returns whether it was actually handed to Resend.

    Never raises: an alert that breaks the thing it is reporting on is worse than a
    missed alert, and this runs inside request handling.
    """
    api_key = os.environ.get("RESEND_API_KEY")
    recipient = os.environ.get("ALERT_EMAIL_TO")
    sender = os.environ.get("ALERT_EMAIL_FROM")
    if not (api_key and recipient and sender):
        log.warning("alert not sent (RESEND_API_KEY/ALERT_EMAIL_* unset): %s", subject)
        return False

    if not _should_send(dedup_key):
        return False

    payload = json.dumps(
        {
            "from": sender,
            "to": [addr.strip() for addr in recipient.split(",") if addr.strip()],
            "subject": subject,
            "text": body,
        }
    ).encode()
    req = urllib.request.Request(
        RESEND_ENDPOINT,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=_SEND_TIMEOUT_SECONDS) as resp:
            return 200 <= resp.status < 300
    except (urllib.error.URLError, OSError, ValueError) as exc:
        log.warning("alert delivery failed: %s", exc)
        return False


def _exception_body(exc: BaseException) -> str:
    return "\n".join(
        [
            f"URL:      {request.method} {request.url}",
            f"Endpoint: {request.endpoint}",
            f"Client:   {request.headers.get('x-forwarded-for', request.remote_addr)}",
            f"Deploy:   {os.environ.get('VERCEL_DEPLOYMENT_ID', 'local')}",
            "",
            "".join(traceback.format_exception(exc)),
        ]
    )


def _dedup_key(exc: BaseException) -> str:
    """Identify the failure by where it was raised, not by which URL tripped over it.

    A database outage raises the same exception from every route; keying on the URL
    would send one mail per page instead of one per outage.
    """
    frames = traceback.extract_tb(exc.__traceback__)
    origin = f"{frames[-1].filename}:{frames[-1].lineno}" if frames else "?"
    return f"{type(exc).__name__}@{origin}"


def install_error_alerts(app: Flask) -> None:
    """Mail the traceback of any unhandled exception, then let Flask 500 as usual.

    Hooked on the signal rather than on `errorhandler(500)` so the response the visitor
    gets is untouched, and so the original exception is still in hand — Flask's error
    handler only receives the `InternalServerError` wrapper.
    """

    def _on_exception(sender: Flask, exception: BaseException, **extra: Any) -> None:
        send_alert(
            f"[velaclasica.ar] {type(exception).__name__} en {request.path}",
            _exception_body(exception),
            dedup_key=_dedup_key(exception),
        )

    # weak=False: blinker holds receivers weakly, and this closure has no other
    # reference — it would be collected before the first exception ever arrived.
    got_request_exception.connect(_on_exception, app, weak=False)
