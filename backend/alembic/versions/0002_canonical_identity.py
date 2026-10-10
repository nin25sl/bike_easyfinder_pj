"""Deduplicate canonical spots by source-stable identity.

Revision ID: 0002_identity
Revises: 0001_mvp
"""
from alembic import op

revision = "0002_identity"
down_revision = "0001_mvp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE spots ADD COLUMN IF NOT EXISTS canonical_key TEXT;
        UPDATE spots s SET canonical_key=c.stable_key
        FROM spot_candidates c WHERE c.id=s.candidate_id AND s.canonical_key IS NULL;

        WITH duplicates AS (
            SELECT id, row_number() OVER (
                PARTITION BY canonical_key ORDER BY verified_at DESC, id
            ) AS ordinal
            FROM spots WHERE canonical_key IS NOT NULL
        )
        UPDATE spots s
        SET publication_status='retired',
            canonical_key=s.canonical_key || ':duplicate:' || s.id::text,
            updated_at=now()
        FROM duplicates d
        WHERE s.id=d.id AND d.ordinal > 1;

        CREATE UNIQUE INDEX IF NOT EXISTS idx_spots_canonical_key ON spots(canonical_key);
        ALTER TABLE spots ALTER COLUMN canonical_key SET NOT NULL;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_spots_canonical_key; ALTER TABLE spots DROP COLUMN IF EXISTS canonical_key;")
