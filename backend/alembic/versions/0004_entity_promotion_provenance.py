"""Promote resolved entities with field-level provenance.

Revision ID: 0004_entity_provenance
Revises: 0003_candidate_history
"""
from alembic import op

revision = "0004_entity_provenance"
down_revision = "0003_candidate_history"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE spots ADD COLUMN IF NOT EXISTS resolved_entity_id UUID
            REFERENCES resolved_spot_entities(id) ON DELETE SET NULL;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_spots_resolved_entity
            ON spots(resolved_entity_id) WHERE resolved_entity_id IS NOT NULL;

        ALTER TABLE spot_sources ADD COLUMN IF NOT EXISTS source_type TEXT;
        ALTER TABLE spot_sources ADD COLUMN IF NOT EXISTS verified_at TIMESTAMPTZ;
        ALTER TABLE spot_sources ADD COLUMN IF NOT EXISTS verification_status TEXT NOT NULL DEFAULT 'unverified';
        ALTER TABLE spot_sources ADD COLUMN IF NOT EXISTS confidence NUMERIC(4,3);

        ALTER TABLE spot_field_sources ADD COLUMN IF NOT EXISTS rule_version TEXT;
        ALTER TABLE spot_field_sources ADD COLUMN IF NOT EXISTS selection_reason JSONB NOT NULL DEFAULT '{}'::jsonb;
        ALTER TABLE spot_field_sources ADD COLUMN IF NOT EXISTS adopted_at TIMESTAMPTZ NOT NULL DEFAULT now();
        ALTER TABLE spot_field_sources ADD COLUMN IF NOT EXISTS is_adopted BOOLEAN NOT NULL DEFAULT false;
        CREATE UNIQUE INDEX IF NOT EXISTS idx_spot_field_sources_one_adopted
            ON spot_field_sources(spot_id, field_name) WHERE is_adopted;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP INDEX IF EXISTS idx_spot_field_sources_one_adopted;
        ALTER TABLE spot_field_sources DROP COLUMN IF EXISTS is_adopted;
        ALTER TABLE spot_field_sources DROP COLUMN IF EXISTS adopted_at;
        ALTER TABLE spot_field_sources DROP COLUMN IF EXISTS selection_reason;
        ALTER TABLE spot_field_sources DROP COLUMN IF EXISTS rule_version;
        ALTER TABLE spot_sources DROP COLUMN IF EXISTS confidence;
        ALTER TABLE spot_sources DROP COLUMN IF EXISTS verification_status;
        ALTER TABLE spot_sources DROP COLUMN IF EXISTS verified_at;
        ALTER TABLE spot_sources DROP COLUMN IF EXISTS source_type;
        DROP INDEX IF EXISTS idx_spots_resolved_entity;
        ALTER TABLE spots DROP COLUMN IF EXISTS resolved_entity_id;
        """
    )
