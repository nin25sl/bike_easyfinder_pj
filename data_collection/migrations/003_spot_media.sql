ALTER TABLE source_registry DROP CONSTRAINT IF EXISTS source_registry_source_type_check;
ALTER TABLE source_registry ADD CONSTRAINT source_registry_source_type_check CHECK (source_type IN (
    'n03', 'osm_overpass', 'osm_pbf', 'public_open_data', 'official_web',
    'general_web', 'touring_media', 'openai_web_discovery', 'manual_seed',
    'wikimedia_commons'
));

CREATE TABLE IF NOT EXISTS media_collection_runs (
    id UUID PRIMARY KEY,
    source_registry_id UUID NOT NULL REFERENCES source_registry(id),
    status TEXT NOT NULL CHECK (status IN ('running', 'partial', 'completed', 'failed', 'cancelled')),
    target_statuses JSONB NOT NULL,
    target_limit INTEGER,
    dry_run BOOLEAN NOT NULL DEFAULT false,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS media_collection_run_items (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES media_collection_runs(id) ON DELETE CASCADE,
    target_kind TEXT NOT NULL CHECK (target_kind IN ('spot', 'entity')),
    target_id UUID NOT NULL,
    target_name TEXT NOT NULL,
    latitude DOUBLE PRECISION,
    longitude DOUBLE PRECISION,
    status TEXT NOT NULL CHECK (status IN ('pending', 'searching', 'ready', 'review_required', 'no_match', 'failed')),
    candidate_count INTEGER NOT NULL DEFAULT 0,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    error_code TEXT,
    error_detail TEXT,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    UNIQUE (run_id, target_kind, target_id)
);
CREATE INDEX IF NOT EXISTS idx_media_run_items_resume ON media_collection_run_items(run_id, status, attempt_count);

CREATE TABLE IF NOT EXISTS spot_media (
    id UUID PRIMARY KEY,
    -- Canonical tables are migrated by the API service after collection migrations.
    -- Integrity for this cross-schema-boundary identifier is enforced by the worker.
    spot_id UUID,
    entity_id UUID REFERENCES resolved_spot_entities(id) ON DELETE CASCADE,
    source_registry_id UUID NOT NULL REFERENCES source_registry(id),
    source_page_id TEXT NOT NULL,
    source_revision_id TEXT,
    source_page_url TEXT NOT NULL,
    original_url TEXT NOT NULL,
    title TEXT NOT NULL,
    creator TEXT NOT NULL,
    license_status TEXT NOT NULL CHECK (license_status IN ('verified', 'prohibited')),
    license_name TEXT NOT NULL,
    license_url TEXT NOT NULL,
    attribution_text TEXT NOT NULL,
    verified_at TIMESTAMPTZ NOT NULL,
    match_score NUMERIC(5,2) NOT NULL CHECK (match_score BETWEEN 0 AND 100),
    distance_meters INTEGER,
    status TEXT NOT NULL CHECK (status IN ('ready', 'review_required', 'rejected', 'suspended')),
    rejection_reason TEXT,
    is_primary BOOLEAN NOT NULL DEFAULT false,
    original_object_key TEXT,
    derivative_object_key TEXT,
    content_hash CHAR(64),
    mime_type TEXT,
    width INTEGER,
    height INTEGER,
    byte_size BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK ((spot_id IS NOT NULL AND entity_id IS NULL) OR (spot_id IS NULL AND entity_id IS NOT NULL)),
    UNIQUE NULLS NOT DISTINCT (source_registry_id, source_page_id, spot_id, entity_id)
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_spot_media_primary_spot ON spot_media(spot_id) WHERE is_primary AND status='ready';
CREATE UNIQUE INDEX IF NOT EXISTS idx_spot_media_primary_entity ON spot_media(entity_id) WHERE is_primary AND status='ready';
CREATE INDEX IF NOT EXISTS idx_spot_media_hash ON spot_media(content_hash) WHERE content_hash IS NOT NULL;

CREATE TABLE IF NOT EXISTS media_collection_candidates (
    run_item_id UUID NOT NULL REFERENCES media_collection_run_items(id) ON DELETE CASCADE,
    media_id UUID NOT NULL REFERENCES spot_media(id) ON DELETE CASCADE,
    rank SMALLINT NOT NULL,
    PRIMARY KEY (run_item_id, media_id)
);
