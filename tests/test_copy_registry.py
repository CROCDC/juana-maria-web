"""The flask-sitecopy registry and the templates that render it must stay in agreement.

These checks are pure (no DB): they are what keep adding editable copy cheap — one
`TextField` plus one `t('<key>')`. They fail loudly when a template asks for a key
nobody declared (an empty heading in production) or a declared key nothing renders (a
dead admin text box).
"""

from __future__ import annotations

from pathlib import Path

from sitecopy.testing import check_registry, check_templates

from app.content.copy_registry import DYNAMIC_COPY_KEYS, REGISTRY
from app.content.rumbos import RUMBOS
from app.content.topics import TOPICS

_APP_DIR = Path(__file__).resolve().parent.parent / "app"


def test_registry_is_sound() -> None:
    assert check_registry(REGISTRY) == []


def test_templates_and_registry_agree() -> None:
    # The topic-card / nav / rumbo keys are built at run time from a slug in a loop, so
    # the literal scan cannot see them — they are the dynamic allow-list.
    assert check_templates(REGISTRY, str(_APP_DIR), dynamic=DYNAMIC_COPY_KEYS) == []


def test_dynamic_topic_keys_are_declared() -> None:
    for topic in TOPICS:
        assert f"topic.{topic.slug}.nav" in REGISTRY.fields
        if topic.is_home:
            continue
        assert f"topic.{topic.slug}.title" in REGISTRY.fields
        assert f"topic.{topic.slug}.cta" in REGISTRY.fields


def test_dynamic_rumbo_keys_are_declared() -> None:
    for rumbo in RUMBOS:
        for suffix in ("name", "where", "body"):
            assert f"rumbo.{rumbo.key}.{suffix}" in REGISTRY.fields
