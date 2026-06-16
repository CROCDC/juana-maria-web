"""HTTP / integration layer — every endpoint, happy path + error paths.

Uses the `client` fixture (a real Flask test client against the real app on the
test DB). The app is a single-page site, so the surface is small: the homepage,
the 404 path, and the response-shaping the factory adds (immutable static caching
in app/factory.py and gzip/brotli via flask-compress).
"""

from __future__ import annotations

from typing import Any


# ----- GET / (happy path) -----------------------------------------------------

def test_index_returns_200_html(client: Any) -> None:
    resp = client.get("/")
    assert resp.status_code == 200
    assert resp.mimetype == "text/html"


def test_index_renders_hero_and_sections(client: Any) -> None:
    body = client.get("/").get_data(as_text=True)
    assert "<h1>Juana María</h1>" in body
    # The dynamic footer year (inject_globals) is rendered server-side.
    assert "Juana María — Argentina" in body
    for anchor in ('id="historia"', 'id="galeria"', 'id="ficha"', 'id="seminarios"'):
        assert anchor in body


# ----- Error paths ------------------------------------------------------------

def test_unknown_path_returns_404(client: Any) -> None:
    resp = client.get("/no-such-page")
    assert resp.status_code == 404


def test_post_to_index_is_method_not_allowed(client: Any) -> None:
    # The index route only registers GET; POST must be rejected, not 500.
    resp = client.post("/")
    assert resp.status_code == 405


# ----- Static asset caching (app/factory.py after_request) --------------------

def test_static_asset_has_immutable_cache_header(client: Any) -> None:
    resp = client.get("/static/css/styles.css")
    assert resp.status_code == 200
    assert resp.headers["Cache-Control"] == "public, max-age=31536000, immutable"


# ----- Compression (flask-compress) -------------------------------------------

def test_html_is_gzip_compressed_when_accepted(client: Any) -> None:
    resp = client.get("/", headers={"Accept-Encoding": "gzip"})
    assert resp.status_code == 200
    assert resp.headers.get("Content-Encoding") == "gzip"


def test_html_is_brotli_compressed_when_accepted(client: Any) -> None:
    resp = client.get("/", headers={"Accept-Encoding": "br"})
    assert resp.status_code == 200
    assert resp.headers.get("Content-Encoding") == "br"
