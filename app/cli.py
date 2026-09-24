"""`flask snapshot …` — the commands that turn the database into the bundled snapshot.

`build` is what the deploy pipeline runs, between the migrations and `vercel deploy`,
so the file it writes is picked up as part of the uploaded source. It is also the
recovery path: the snapshot is derived from Postgres and can always be regenerated
from it, by hand, without a deploy.
"""

from __future__ import annotations

import click
from flask import Flask
from flask.cli import AppGroup
from sitecopy import SQLAlchemyStore

from app import snapshot
from app.content.topics import DEFAULT_ENABLED
from app.factory import db
from app.repositories.topic_visibility_repository import TopicVisibilityRepository


def register_cli(app: Flask) -> None:
    group = AppGroup("snapshot", help="Build and inspect the bundled content snapshot.")

    @group.command("build")
    def build() -> None:
        """Read the live content from the database and write app/content/snapshot.json."""
        # The real store, not the app's snapshot-backed one: reading the snapshot to
        # build the snapshot would freeze the site's content at whatever shipped.
        store = SQLAlchemyStore(db)
        TopicVisibilityRepository.ensure_seeded(DEFAULT_ENABLED)
        visibility = TopicVisibilityRepository.get_state_map()

        data = snapshot.build(store, visibility)
        path = snapshot.write(data)
        click.echo(
            f"wrote {path}: {len(data['texts'])} texts, "
            f"{sum(data['topic_visibility'].values())} of "
            f"{len(data['topic_visibility'])} topics published"
        )

    @group.command("show")
    def show() -> None:
        """What this deployment would actually serve."""
        data = snapshot.load()
        if data is None:
            click.echo("no usable snapshot bundled; public reads fall back to the database")
            return
        click.echo(f"generated_at: {data['generated_at']}")
        click.echo(f"texts:        {len(data['texts'])}")
        for slug, enabled in sorted(data["topic_visibility"].items()):
            click.echo(f"  {'x' if enabled else ' '} {slug}")

    app.cli.add_command(group)
