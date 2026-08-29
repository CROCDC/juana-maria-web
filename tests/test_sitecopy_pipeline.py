"""With text sizes on, the editor's response rewrite has to reach the public HTML.

flask-sitecopy renders a size by rewriting the finished response, and Flask runs
``after_request`` hooks in REVERSE registration order — so Compress must be wired
BEFORE ``SiteCopy(...)`` in :mod:`app.factory`, or the private-use markers the rewrite
was going to replace ship to the browser as little empty boxes. Until 0.5 that was only
ever visible to an admin in ``?edit=1``; with sizes on it would hit every visitor of
every page, which is why it is guarded here rather than left to a code comment.

The second test is the other half of the same feature: a sized value arrives wrapped in
a new element (``<span class="sc-s …">``, a ``<div>`` for a ``rich`` value), and the
site's own CSS has to keep working around it.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import pytest
from sitecopy.testing import check_response_pipeline

# The size the tests stage. Any token of the scale would do; `lg` is the first step up.
SIZE = "lg"


@contextmanager
def staged_size(app: Any, key: str, token: str) -> Iterator[None]:
    """Publish a size for ``key``, and put the store back the way it was."""
    from sitecopy.resolver import save
    from sitecopy.sizes import size_key
    from sitecopy.state import current_store

    row = size_key(key)
    with app.app_context():
        store = current_store()
        before = store.get(row)
        store.set_published(row, token)
        save()
    try:
        yield
    finally:
        with app.app_context():
            store = current_store()
            if before is None:
                store.delete(row)
            else:
                store.set_published(row, before.published_value)
                store.set_draft(row, before.draft_value)
            save()


@pytest.mark.parametrize(
    ("path", "key"),
    [
        # A key the page itself renders, not just the shared header — a rewrite that
        # only ever reached base.html would still look healthy.
        ("/", "home.hero.title"),
        ("/crew-program", "crew.lead"),
    ],
)
def test_the_rewrite_still_sees_the_html(
    app_instance: Any, db_clean: None, path: str, key: str
) -> None:
    assert check_response_pipeline(app_instance, path, key=key) == []


def test_every_page_the_editor_offers_is_covered(app_instance: Any, db_clean: None) -> None:
    """Whatever page the editor can open, a visitor of it must get a clean response.

    Driven off the editor's own page list, so a topic published later is checked without
    anyone remembering to add it here. `global.brand` is the site's name in the header,
    so it is visible text on every one of them.
    """
    from app.factory import _editor_pages

    with app_instance.app_context():
        paths = [page["path"] for page in _editor_pages()]

    assert paths, "the editor offers no page at all"
    for path in paths:
        assert check_response_pipeline(app_instance, path, key="global.brand") == [], path


def test_a_size_wraps_the_value_without_breaking_the_prose(
    app_instance: Any, db_clean: None
) -> None:
    """A sized `rich` value arrives as a <div>, with its paragraphs still siblings.

    `.prose p + p` (styles.css) is a descendant selector, so it keeps matching through
    the wrapper — this pins that down, since the CSS and the wrapper are decided in two
    different repositories. A `>` combinator there would have been the thing to catch.
    """
    wrapper = f'<div class="sc-s-block sc-s-{SIZE}">'

    with staged_size(app_instance, "crew.body", SIZE):
        html = app_instance.test_client().get("/crew-program").get_data(as_text=True)

    assert wrapper in html
    assert '<div class="prose reveal">' in html.split(wrapper, 1)[0]
    inside = html.split(wrapper, 1)[1].split("</div>", 1)[0]
    assert inside.count("<p>") >= 2, "the rich value lost its paragraphs inside the wrapper"


def test_a_page_with_no_size_is_untouched(app_instance: Any, db_clean: None) -> None:
    """Sizes cost nothing where nobody set one: no wrapper, no injected stylesheet."""
    html = app_instance.test_client().get("/").get_data(as_text=True)

    assert "sc-s" not in html
