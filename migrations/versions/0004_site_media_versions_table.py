"""site_media_versions: flask-sitecopy media version history table

Revision ID: 0004_site_media_versions
Revises: 0003_site_texts
Create Date: 2026-08-13 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0004_site_media_versions'
down_revision = '0003_site_texts'
branch_labels = None
depends_on = None


def upgrade():
    # History of the URLs each image/video field has pointed at, so the editor's
    # version gallery can roll a picture or clip back to an earlier one (flask-sitecopy
    # 0.4). One row per (key, url); only the URL is remembered, never the bytes. Empty
    # on a fresh deploy — a field with no history just shows its current value.
    # Matches sitecopy.media.build_media_model('site_media_versions').
    #
    # Guarded like site_texts: created only if absent, so it is a safe no-op if the
    # table was ever built by sitecopy.ensure_schema() outside of migrations.
    bind = op.get_bind()
    if 'site_media_versions' in set(sa.inspect(bind).get_table_names()):
        return

    op.create_table(
        'site_media_versions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('key', sa.String(length=190), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(
        op.f('ix_site_media_versions_key'), 'site_media_versions', ['key'], unique=False
    )


def downgrade():
    op.drop_index(op.f('ix_site_media_versions_key'), table_name='site_media_versions')
    op.drop_table('site_media_versions')
