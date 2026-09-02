"""Local development server. Production runs `wsgi:app` as a Vercel Function."""

import os

from app import app

if __name__ == "__main__":
    debug = os.environ.get("FLASK_DEBUG", "1") not in ("0", "false", "False", "")
    app.run(host="0.0.0.0", port=7017, debug=debug)
