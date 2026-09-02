"""Entrypoint Vercel loads as the Vercel Function.

Vercel's Flask preset looks for a top-level ``app`` in one of a fixed set of
filenames (``wsgi.py`` among them) — hence this module instead of ``run.py``,
whose Prometheus/psutil instrumentation only makes sense for the long-lived
gunicorn process on the local server.
"""

from app import app

__all__ = ["app"]
