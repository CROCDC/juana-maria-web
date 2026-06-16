from flask import Flask, Response, render_template, request


def register_routes(app: Flask) -> None:
    @app.route("/")
    def index() -> str:
        # is_index lets base.html keep bare "#section" anchors here (smooth
        # in-page scroll) while other pages get "/#section" that resolve home.
        return render_template("index.html", is_index=True)

    @app.route("/robots.txt")
    def robots() -> Response:
        body = f"User-agent: *\nAllow: /\nSitemap: {request.url_root}sitemap.xml\n"
        return Response(body, mimetype="text/plain")

    @app.route("/sitemap.xml")
    def sitemap() -> Response:
        # Single-page site: one URL, domain taken from the request.
        body = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
            f"  <url><loc>{request.url_root}</loc>"
            "<changefreq>monthly</changefreq><priority>1.0</priority></url>\n"
            "</urlset>\n"
        )
        return Response(body, mimetype="application/xml")

    @app.errorhandler(404)
    def not_found(_error: object) -> tuple[str, int]:
        return render_template("404.html"), 404
