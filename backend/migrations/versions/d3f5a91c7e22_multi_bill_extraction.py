"""Add reference_number to bills, allow multiple documents per storage_key

Revision ID: d3f5a91c7e22
Revises: c19b4f2d8e01
Create Date: 2026-08-23 00:00:00.000000

Two changes to support extracting several bills out of a single uploaded
document (e.g. a one-page "monthly expenses" summary listing Electric,
Water, Internet, and Insurance as separate charges):

1. `bill_definitions.reference_number` -- a new nullable column for the
   invoice/account/customer number, if the document has one. Purely
   additive, no backfill needed.
2. `bill_documents.storage_key` drops its unique constraint and gains a
   plain index instead. Multiple bills extracted from one uploaded file
   now get one BillDocument metadata row each, all pointing at the same
   storage_key (the underlying bytes are stored exactly once either way)
   -- so every resulting bill still links back to the original document.
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'd3f5a91c7e22'
down_revision = 'c19b4f2d8e01'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('bill_definitions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('reference_number', sa.String(length=100), nullable=True))

    with op.batch_alter_table('bill_documents', schema=None) as batch_op:
        batch_op.drop_constraint('bill_documents_storage_key_key', type_='unique')
        batch_op.create_index(batch_op.f('ix_bill_documents_storage_key'), ['storage_key'], unique=False)


def downgrade():
    with op.batch_alter_table('bill_documents', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_bill_documents_storage_key'))
        batch_op.create_unique_constraint('bill_documents_storage_key_key', ['storage_key'])

    with op.batch_alter_table('bill_definitions', schema=None) as batch_op:
        batch_op.drop_column('reference_number')
