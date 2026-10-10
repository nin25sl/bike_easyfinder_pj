"""Allow retired canonical rows to retain their original candidate reference.

Revision ID: 0003_candidate_history
Revises: 0002_identity
"""
from alembic import op

revision = "0003_candidate_history"
down_revision = "0002_identity"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE spots DROP CONSTRAINT IF EXISTS spots_candidate_id_key")
    op.execute("CREATE INDEX IF NOT EXISTS idx_spots_candidate_id ON spots(candidate_id)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_spots_candidate_id")
    op.execute("ALTER TABLE spots ADD CONSTRAINT spots_candidate_id_key UNIQUE(candidate_id)")

