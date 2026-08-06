"""site_texts: flask-sitecopy overrides table

Revision ID: 0003_site_texts
Revises: 0002_crew_form_fields
Create Date: 2026-08-06 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0003_site_texts'
down_revision = '0002_crew_form_fields'
branch_labels = None
depends_on = None


def upgrade():
    # The overrides table for flask-sitecopy: one row per key that has been edited,
    # holding the published/draft/previous values. A key with no row renders its
    # registry default, so this table is empty on a fresh deploy and the site looks
    # exactly like the code. Matches sitecopy.storage.build_model('site_texts').
    #
    # Guarded like the baseline: created only if absent, so it is a safe no-op if the
    # table was ever built by sitecopy.ensure_schema() outside of migrations.
    bind = op.get_bind()
    if 'site_texts' in set(sa.inspect(bind).get_table_names()):
        return

    op.create_table(
        'site_texts',
        sa.Column('key', sa.String(length=190), nullable=False),
        sa.Column('published_value', sa.Text(), nullable=True),
        sa.Column('draft_value', sa.Text(), nullable=True),
        sa.Column('previous_value', sa.Text(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('key'),
    )


def downgrade():
    op.drop_table('site_texts')
