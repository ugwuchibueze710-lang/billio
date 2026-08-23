"""Switch auth to Supabase (drop local password/token storage)

Revision ID: c19b4f2d8e01
Revises: b2a527e102d4
Create Date: 2026-08-23 00:00:00.000000

This migration deletes any existing rows in `users` (and everything that
cascades from them) before adding the new NOT NULL Supabase columns. That's
safe pre-launch: the only accounts that could exist on a deploy that has
only ever run the initial schema are test signups made while wiring up the
app, never real user data. If you've since put real users on this
deployment, back up first -- this is destructive.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'c19b4f2d8e01'
down_revision = 'b2a527e102d4'
branch_labels = None
depends_on = None


def upgrade():
    # Wipe existing users (and cascaded rows) so the new NOT NULL columns
    # below can be added without a backfill step -- see module docstring.
    op.execute("DELETE FROM users")

    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('supabase_user_id', sa.String(length=64), nullable=False))
        batch_op.add_column(sa.Column('supabase_login_email', sa.String(length=255), nullable=False))
        batch_op.create_unique_constraint('uq_users_supabase_user_id', ['supabase_user_id'])
        batch_op.drop_column('password_hash')
        batch_op.drop_column('token_version')

    with op.batch_alter_table('token_blocklist', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_token_blocklist_user_id'))
        batch_op.drop_index(batch_op.f('ix_token_blocklist_jti'))
    op.drop_table('token_blocklist')


def downgrade():
    op.create_table(
        'token_blocklist',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('jti', sa.String(length=36), nullable=False),
        sa.Column('token_type', sa.String(length=10), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('revoked_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('token_blocklist', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_token_blocklist_jti'), ['jti'], unique=True)
        batch_op.create_index(batch_op.f('ix_token_blocklist_user_id'), ['user_id'], unique=False)

    op.execute("DELETE FROM users")
    with op.batch_alter_table('users', schema=None) as batch_op:
        batch_op.add_column(sa.Column('password_hash', sa.Text(), nullable=False))
        batch_op.add_column(sa.Column('token_version', sa.Integer(), nullable=False, server_default='0'))
        batch_op.drop_constraint('uq_users_supabase_user_id', type_='unique')
        batch_op.drop_column('supabase_login_email')
        batch_op.drop_column('supabase_user_id')
