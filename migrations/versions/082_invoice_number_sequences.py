"""Separate tax and non-tax invoice number series

Tax and non-tax invoices previously shared the same timestamp-based "INV..."
number. They now have independent running sequences, and existing VPS tax
invoices are repaired by scripts/repair_invoice_numbers.py after deployment.

Idempotent because the VPS databases have historically drifted from the
Alembic chain.

Revision ID: 082
Revises: 081
Create Date: 2026-11-23
"""
from alembic import op

revision = "082"
down_revision = "081"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS invoice_number_sequences (
            id             UUID PRIMARY KEY,
            series_key     VARCHAR(80) NOT NULL UNIQUE,
            prefix         VARCHAR(20) NOT NULL,
            invoice_year   INTEGER NOT NULL,
            invoice_kind   VARCHAR(10) NOT NULL,
            last_number    INTEGER NOT NULL DEFAULT 0,
            created_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at     TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            is_active      BOOLEAN DEFAULT TRUE
        );
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_invoice_number_sequences_kind_year
            ON invoice_number_sequences (invoice_kind, invoice_year);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS invoice_number_sequences;")
