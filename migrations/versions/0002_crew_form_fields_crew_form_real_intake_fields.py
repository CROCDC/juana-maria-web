"""crew form: real intake fields

Revision ID: 0002_crew_form_fields
Revises: 0001_baseline
Create Date: 2026-06-28 21:52:16.568613

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0002_crew_form_fields'
down_revision = '0001_baseline'
branch_labels = None
depends_on = None


def upgrade():
    # Reworks the crew_applications table to the client's actual intake questions.
    # The two new REQUIRED columns get a temporary server_default so the ALTER
    # succeeds on the live table (which already has applications); the default is
    # then dropped so the column matches the model (NOT NULL, value always
    # supplied by the app). Existing rows keep '' / false for these fields.
    op.add_column('crew_applications', sa.Column('whatsapp', sa.String(length=40), nullable=False, server_default=''))
    op.add_column('crew_applications', sa.Column('instagram', sa.String(length=80), nullable=True))
    op.add_column('crew_applications', sa.Column('is_adult', sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column('crew_applications', sa.Column('preferred_date', sa.String(length=120), nullable=True))
    op.add_column('crew_applications', sa.Column('preferred_route', sa.String(length=80), nullable=True))

    op.alter_column('crew_applications', 'whatsapp', server_default=None)
    op.alter_column('crew_applications', 'is_adult', server_default=None)

    op.drop_column('crew_applications', 'phone')
    op.drop_column('crew_applications', 'experience')


def downgrade():
    # Re-add the dropped columns as nullable (their old values are not recovered).
    op.add_column('crew_applications', sa.Column('experience', sa.String(length=40), nullable=True))
    op.add_column('crew_applications', sa.Column('phone', sa.String(length=40), nullable=True))
    op.drop_column('crew_applications', 'preferred_route')
    op.drop_column('crew_applications', 'preferred_date')
    op.drop_column('crew_applications', 'is_adult')
    op.drop_column('crew_applications', 'instagram')
    op.drop_column('crew_applications', 'whatsapp')
