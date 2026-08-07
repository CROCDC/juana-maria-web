"""The site's admin session, in one place so both the routes and flask-sitecopy share it.

`is_logged_in` answers "is this request an admin?" and `login_required` guards a view by
bouncing anonymous visitors to the login. flask-sitecopy needs both: the predicate gates
preview/edit mode on every public page, the decorator guards its panel — so the content
editor reuses the very same session the rest of `/admin` already uses.
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any

from flask import redirect, request, session, url_for


def is_logged_in() -> bool:
    return bool(session.get("is_admin"))


def login_required(view: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(view)
    def wrapped(*args: Any, **kwargs: Any) -> Any:
        if not is_logged_in():
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)

    return wrapped
