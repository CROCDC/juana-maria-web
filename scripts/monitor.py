#!/usr/bin/env python3
"""Synthetic checks for the live site, mailed out when something breaks.

Runs on a GitHub Actions schedule (`.github/workflows/monitor.yml`), not on Vercel:
the whole point is to notice when the deploy itself cannot answer, which something
running inside it cannot do.

Deliberately stdlib-only and self-contained. It shares no code with `app/alerts.py`
even though both post to Resend, because importing the package would pull in Flask,
SQLAlchemy and a DATABASE_URL on a runner that needs none of them — and would make
the watchdog fail for the same reasons as the thing it watches.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
from typing import Any

RESEND_ENDPOINT = "https://api.resend.com/emails"
NEON_API = "https://console.neon.tech/api/v2"

DEFAULT_PATHS = "/,/routes,/crew-program,/historic-sailings,/sitemap.xml"

# A 500 from a Vercel Function can take a while to come back; the whole run is cheap,
# so wait long enough that a slow cold start is not reported as an outage.
HTTP_TIMEOUT = 20


def env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


# --------------------------------------------------------------------------- mail


def send_mail(subject: str, body: str) -> bool:
    api_key, to, sender = env("RESEND_API_KEY"), env("ALERT_EMAIL_TO"), env("ALERT_EMAIL_FROM")
    if not (api_key and to and sender):
        print("!! RESEND_API_KEY/ALERT_EMAIL_* unset — not mailing:", subject)
        return False
    payload = json.dumps(
        {
            "from": sender,
            "to": [a.strip() for a in to.split(",") if a.strip()],
            "subject": subject,
            "text": body,
        }
    ).encode()
    req = urllib.request.Request(
        RESEND_ENDPOINT,
        data=payload,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            print(f"mail sent ({resp.status}): {subject}")
            return True
    except urllib.error.HTTPError as exc:
        print(f"!! mail rejected ({exc.code}): {exc.read()[:300]!r}")
    except (urllib.error.URLError, OSError) as exc:
        print(f"!! mail failed: {exc}")
    return False


# ------------------------------------------------------------------------- checks


def fetch(url: str) -> tuple[int, str]:
    req = urllib.request.Request(url, headers={"User-Agent": "velaclasica-monitor/1"})
    try:
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            return resp.status, resp.read(4000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read(4000).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as exc:
        return 0, str(exc)


def check_pages(base: str, paths: list[str]) -> list[str]:
    failures = []
    for path in paths:
        status, _ = fetch(base + path)
        print(f"  {status:>3}  {path}")
        if status != 200:
            failures.append(f"{path} respondió {status or 'sin conexión'}")
    return failures


def check_health(base: str, *, deep: bool) -> list[str]:
    url = f"{base}/healthz" if deep else f"{base}/healthz?db=0"
    status, body = fetch(url)
    print(f"  {status:>3}  {url.removeprefix(base)}  {body[:200]}")
    if status == 200:
        return []
    try:
        checks = json.loads(body).get("checks", {})
        detail = "; ".join(f"{k}: {v}" for k, v in checks.items() if v != "ok")
    except ValueError:
        detail = body[:300]
    return [f"/healthz respondió {status or 'sin conexión'} — {detail or 'sin detalle'}"]


def check_neon_quota() -> tuple[list[str], str | None]:
    """Warn before Neon's quota suspends the compute, which is what took the site down.

    Free plan allowances are not returned by the API (the `quota` object only holds
    limits somebody set by hand), so the thresholds are configuration here.
    """
    api_key, project_id = env("NEON_API_KEY"), env("NEON_PROJECT_ID")
    if not (api_key and project_id):
        print("  (Neon quota check skipped: NEON_API_KEY/NEON_PROJECT_ID unset)")
        return [], None

    def get(path: str) -> dict[str, Any]:
        req = urllib.request.Request(
            f"{NEON_API}{path}",
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=HTTP_TIMEOUT) as resp:
            data: dict[str, Any] = json.loads(resp.read())
            return data

    try:
        project = get(f"/projects/{project_id}").get("project", {})
        branches = get(f"/projects/{project_id}/branches").get("branches", [])
    except (urllib.error.URLError, OSError, ValueError) as exc:
        # Not a quota warning: saying "close to the limit" when the truth is "could not
        # ask" is how an alert channel stops being believed.
        print(f"!! no se pudo leer la cuota de Neon: {exc}")
        return [], f"no se pudo leer la cuota de Neon: {exc}"

    warn_at = env_float("NEON_QUOTA_WARN_PCT", 80) / 100
    used = {
        "compute (CU-hours)": (
            project.get("compute_time_seconds", 0) / 3600,
            env_float("NEON_COMPUTE_HOURS_LIMIT", 100),
        ),
        "transfer (GB)": (
            project.get("data_transfer_bytes", 0) / 1e9,
            env_float("NEON_TRANSFER_GB_LIMIT", 5),
        ),
        "storage (GB)": (
            max((b.get("logical_size", 0) for b in branches), default=0) / 1e9,
            env_float("NEON_STORAGE_GB_LIMIT", 0.5),
        ),
    }

    warnings = []
    for label, (value, limit) in used.items():
        pct = value / limit if limit else 0
        print(f"  neon {label}: {value:.2f} / {limit:.2f} ({pct:.0%})")
        if pct >= warn_at:
            warnings.append(f"Neon {label}: {value:.2f} de {limit:.2f} ({pct:.0%})")
    if warnings:
        period = project.get("consumption_period_end", "?")
        warnings.append(f"El período de consumo cierra el {period}.")
    return warnings, None


# -------------------------------------------------------------------------- state


def read_state(path: str) -> dict[str, Any]:
    try:
        with open(path, encoding="utf-8") as fh:
            state: dict[str, Any] = json.load(fh)
            return state
    except (OSError, ValueError):
        return {}


def write_state(path: str, state: dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(state, fh)


# --------------------------------------------------------------------------- main


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--deep",
        action="store_true",
        help="hit the database through /healthz and read Neon's quota",
    )
    args = parser.parse_args()

    base = env("MONITOR_BASE_URL", "https://velaclasica.ar").rstrip("/")
    paths = [p.strip() for p in env("MONITOR_PATHS", DEFAULT_PATHS).split(",") if p.strip()]
    state_file = env("MONITOR_STATE_FILE", ".monitor-state/state.json")

    print(f"== {'deep' if args.deep else 'shallow'} check of {base}")
    failures = check_health(base, deep=args.deep) + check_pages(base, paths)
    quota_warnings, quota_error = check_neon_quota() if args.deep else ([], None)

    state = read_state(state_file)
    was_down = bool(state.get("down"))
    now = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())

    if failures and not was_down:
        send_mail(
            f"🔴 {base} caído",
            "\n".join(
                [f"Detectado: {now}", "", *(f"  • {f}" for f in failures), "",
                 f"Logs: vercel logs {base}", f"Run:  {env('RUN_URL', '(local)')}"]
            ),
        )
        state = {"down": True, "since": now, "failures": failures}
    elif failures:
        print(f"still down since {state.get('since')} — already notified")
        state["failures"] = failures
    elif was_down:
        send_mail(
            f"🟢 {base} recuperado",
            f"Recuperado: {now}\nCaído desde: {state.get('since')}\n\n"
            + "\n".join(f"  • {f}" for f in state.get("failures", [])),
        )
        state = {"down": False}
    else:
        print("all checks passed")
        state = {"down": False}

    # Quota warnings are throttled to one a day: nothing gets better between runs, and
    # the point is to be reminded before the reset, not every hour.
    today = time.strftime("%Y-%m-%d", time.gmtime())
    subject, body = None, ""
    if quota_warnings:
        subject = f"🟠 {base}: cuota de Neon cerca del límite"
        body = "\n".join(quota_warnings)
    elif quota_error:
        subject = f"🟠 {base}: no se pudo leer la cuota de Neon"
        body = f"{quota_error}\n\nEl chequeo de cuota quedó ciego; el resto del monitor sigue andando."

    if subject and state.get("quota_warned_on") != today:
        if send_mail(subject, body):
            state["quota_warned_on"] = today
    elif not subject and args.deep:
        state.pop("quota_warned_on", None)

    write_state(state_file, state)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
