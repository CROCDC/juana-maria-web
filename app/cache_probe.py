"""Temporary probes for why Vercel's CDN never stores this app's responses.

Three attempts at fixing it from the outside failed (`Vary: Cookie`, then the targeted
`Vercel-CDN-Cache-Control` pair), and the runtime logs report `cacheReason: ""` — no
reason at all, which rules out the two documented causes and names no third. So this
stops guessing and measures: each route strips one more thing off a normal page, and
the pattern of HIT vs MISS says which one matters.

| route | format | cache header | pipeline |
|---|---|---|---|
| `/__cache/plain` | text/plain | bare `s-maxage`, the form Vercel documents | none |
| `/__cache/targeted` | text/plain | the targeted pair production uses | none |
| `/__cache/length` | text/plain | bare `s-maxage` | explicit `Content-Length` |
| `/__cache/html` | text/html | bare `s-maxage` | string, no template |
| `/__cache/render` | text/html | bare `s-maxage` | the real template stack |

Delete this module and its registration once the answer is in — see
docs/deploy/MONITORING.md.
"""

from __future__ import annotations

from flask import Flask, Response, render_template

# Short, so a wrong guess does not pin a probe for a day while testing.
PROBE_SECONDS = 600

_SHARED = f"public, s-maxage={PROBE_SECONDS}, stale-while-revalidate=60"

BODY = "cache probe\n"


def _probe(body: str, mimetype: str) -> Response:
    response = Response(body, mimetype=mimetype)
    # Every probe is noindex: these URLs exist to be curl'd, not found.
    response.headers["X-Robots-Tag"] = "noindex, nofollow"
    return response


def register_cache_probes(app: Flask) -> None:
    @app.route("/__cache/plain")
    def probe_plain() -> Response:
        """The exact shape Vercel's own examples use. If even this misses, nothing the
        application does to its headers can be the cause."""
        response = _probe(BODY, "text/plain")
        response.headers["Cache-Control"] = _SHARED
        return response

    @app.route("/__cache/targeted")
    def probe_targeted() -> Response:
        response = _probe(BODY, "text/plain")
        response.headers["Cache-Control"] = "public, max-age=0, must-revalidate"
        response.headers["CDN-Cache-Control"] = _SHARED
        response.headers["Vercel-CDN-Cache-Control"] = _SHARED
        return response

    @app.route("/__cache/length")
    def probe_length() -> Response:
        """Production's pages come back with no `Content-Length` and no `ETag`, while
        the static files that do cache have both — the one structural difference found
        so far. This asks whether the length survives the Python runtime at all."""
        response = _probe(BODY, "text/plain")
        response.headers["Cache-Control"] = _SHARED
        response.headers["Content-Length"] = str(len(BODY))
        response.headers["ETag"] = '"cache-probe"'
        return response

    @app.route("/__cache/html")
    def probe_html() -> Response:
        response = _probe("<!doctype html><title>probe</title>probe\n", "text/html")
        response.headers["Cache-Control"] = _SHARED
        return response

    @app.route("/__cache/render")
    def probe_render() -> Response:
        """The whole real stack — Jinja, sitecopy's rewrite, compression, the session
        read. The only difference from `/` is that the header is set here."""
        response = _probe(render_template("404.html"), "text/html")
        response.headers["Cache-Control"] = _SHARED
        return response
