"""Add domain_legal_pages table (admin-managed privacy / terms / refund copy)

Google Play rejected Bibek Pro + Palei Pro (Aug 30, 2026) because the privacy
policy did not disclose Location collection. The copy was hardcoded inside each
Next.js site, so fixing it required a code change per site. This table moves
legal copy into the DB so Admin Dashboard → Domains → Legal owns it and both
brands stay in sync from one backend image.

Idempotent (CREATE TABLE / INDEX IF NOT EXISTS) so it is safe to re-run against
the VPS databases, which have historically drifted from the migration chain.

Revision ID: 081
Revises: 080
Create Date: 2026-09-04
"""
from alembic import op

revision = '081'
down_revision = '080'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS domain_legal_pages (
            id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            domain_id        UUID NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
            page_key         VARCHAR(50)  NOT NULL,
            title            VARCHAR(200) NOT NULL,
            subtitle         TEXT,
            sections_json    TEXT,
            footer_note      TEXT,
            effective_date   VARCHAR(50),
            meta_title       VARCHAR(200),
            meta_description TEXT,
            robots           VARCHAR(100) DEFAULT 'index,follow',
            is_published     BOOLEAN      NOT NULL DEFAULT TRUE,
            created_at       TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
            updated_at       TIMESTAMP WITH TIME ZONE DEFAULT now(),
            is_active        BOOLEAN DEFAULT TRUE
        );
    """)

    # One row per (domain, page) — the seeder and the admin upsert both rely on
    # this constraint to stay idempotent.
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uq_domain_legal_page
            ON domain_legal_pages (domain_id, page_key);
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS ix_domain_legal_pages_domain_id
            ON domain_legal_pages (domain_id);
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS domain_legal_pages;")
