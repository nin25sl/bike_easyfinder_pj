ALTER TABLE source_registry DROP CONSTRAINT IF EXISTS source_registry_source_type_check;
ALTER TABLE source_registry ADD CONSTRAINT source_registry_source_type_check CHECK (source_type IN (
    'n03', 'osm_overpass', 'osm_pbf', 'public_open_data', 'official_web',
    'general_web', 'touring_media', 'openai_web_discovery', 'manual_seed'
));

CREATE TABLE IF NOT EXISTS collection_batches (
    id UUID PRIMARY KEY,
    profile_name TEXT NOT NULL,
    region_group TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('initial', 'refresh')),
    status TEXT NOT NULL CHECK (status IN (
        'queued', 'running', 'partial', 'completed', 'failed', 'cancelled'
    )),
    requested_regions JSONB NOT NULL,
    requested_sources JSONB NOT NULL,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

ALTER TABLE collection_runs ADD COLUMN IF NOT EXISTS batch_id UUID REFERENCES collection_batches(id);
CREATE INDEX IF NOT EXISTS idx_collection_runs_batch ON collection_runs(batch_id);

CREATE TABLE IF NOT EXISTS resolved_spot_entities (
    id UUID PRIMARY KEY,
    region_id UUID NOT NULL REFERENCES administrative_regions(id),
    entity_key TEXT NOT NULL UNIQUE,
    representative_candidate_id UUID REFERENCES spot_candidates(id),
    status TEXT NOT NULL CHECK (status IN ('draft', 'ready', 'review_required', 'rejected', 'superseded')),
    quality_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (quality_score BETWEEN 0 AND 100),
    resolution_rule_version TEXT NOT NULL,
    merged_into_entity_id UUID REFERENCES resolved_spot_entities(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_resolved_entities_region ON resolved_spot_entities(region_id, status);

CREATE TABLE IF NOT EXISTS spot_entity_memberships (
    entity_id UUID NOT NULL REFERENCES resolved_spot_entities(id) ON DELETE CASCADE,
    candidate_id UUID NOT NULL UNIQUE REFERENCES spot_candidates(id) ON DELETE CASCADE,
    match_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (match_score BETWEEN 0 AND 100),
    decision TEXT NOT NULL CHECK (decision IN ('seed', 'auto', 'manual_approved', 'manual_rejected')),
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    rule_version TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, candidate_id)
);
CREATE INDEX IF NOT EXISTS idx_entity_memberships_entity ON spot_entity_memberships(entity_id);

CREATE TABLE IF NOT EXISTS entity_field_selections (
    entity_id UUID NOT NULL REFERENCES resolved_spot_entities(id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    observation_id UUID NOT NULL REFERENCES field_observations(id) ON DELETE CASCADE,
    selection_score NUMERIC(6,2) NOT NULL,
    rule_version TEXT NOT NULL,
    selection_reason JSONB NOT NULL DEFAULT '{}'::jsonb,
    selected_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (entity_id, field_name)
);

ALTER TABLE review_tasks ADD COLUMN IF NOT EXISTS entity_id UUID REFERENCES resolved_spot_entities(id) ON DELETE CASCADE;
ALTER TABLE review_tasks ALTER COLUMN candidate_id DROP NOT NULL;
ALTER TABLE review_tasks DROP CONSTRAINT IF EXISTS review_tasks_target_check;
ALTER TABLE review_tasks ADD CONSTRAINT review_tasks_target_check CHECK (
    (candidate_id IS NOT NULL AND entity_id IS NULL) OR
    (candidate_id IS NULL AND entity_id IS NOT NULL)
);
DROP INDEX IF EXISTS idx_review_tasks_open_unique;
CREATE UNIQUE INDEX IF NOT EXISTS idx_review_tasks_candidate_open_unique
    ON review_tasks (candidate_id, reason_code, COALESCE(observation_id, '00000000-0000-0000-0000-000000000000'::uuid))
    WHERE status = 'open' AND candidate_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_review_tasks_entity_open_unique
    ON review_tasks (entity_id, reason_code, COALESCE(observation_id, '00000000-0000-0000-0000-000000000000'::uuid))
    WHERE status = 'open' AND entity_id IS NOT NULL;

ALTER TABLE raw_documents ADD COLUMN IF NOT EXISTS source_etag TEXT;
ALTER TABLE raw_documents ADD COLUMN IF NOT EXISTS source_last_modified TEXT;
ALTER TABLE raw_documents ADD COLUMN IF NOT EXISTS unchanged BOOLEAN NOT NULL DEFAULT false;
ALTER TABLE field_observations ADD COLUMN IF NOT EXISTS rule_version TEXT;
