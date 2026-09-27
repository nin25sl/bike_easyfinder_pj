CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS source_registry (
    id UUID PRIMARY KEY,
    source_key TEXT NOT NULL UNIQUE,
    source_type TEXT NOT NULL CHECK (source_type IN (
        'n03', 'osm_overpass', 'osm_pbf', 'public_open_data',
        'official_web', 'openai_web_discovery', 'manual_seed'
    )),
    base_url TEXT,
    domain TEXT,
    approval_status TEXT NOT NULL CHECK (approval_status IN (
        'pending_review', 'approved', 'suspended', 'retired', 'rejected'
    )),
    license_status TEXT NOT NULL CHECK (license_status IN (
        'verified', 'restricted', 'unknown', 'prohibited'
    )),
    license_name TEXT,
    terms_url TEXT,
    attribution_text TEXT,
    robots_checked_at TIMESTAMPTZ,
    raw_storage_policy TEXT NOT NULL CHECK (raw_storage_policy IN (
        'full_allowed', 'facts_only', 'metadata_only', 'prohibited'
    )),
    refresh_interval_days INTEGER,
    rate_limit_per_minute INTEGER NOT NULL CHECK (rate_limit_per_minute > 0),
    request_timeout_seconds INTEGER NOT NULL CHECK (request_timeout_seconds > 0),
    max_pages_per_run INTEGER NOT NULL CHECK (max_pages_per_run > 0),
    config JSONB NOT NULL DEFAULT '{}'::jsonb,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS administrative_regions (
    id UUID PRIMARY KEY,
    region_code VARCHAR(5) NOT NULL,
    region_kind TEXT NOT NULL CHECK (region_kind IN (
        'prefecture', 'municipality', 'designated_city', 'ward'
    )),
    name_ja TEXT NOT NULL,
    prefecture_code CHAR(2) NOT NULL,
    parent_region_code VARCHAR(5),
    geometry GEOMETRY(MultiPolygon, 4326) NOT NULL,
    dataset_version TEXT NOT NULL,
    valid_from DATE NOT NULL,
    source_registry_id UUID NOT NULL REFERENCES source_registry(id),
    is_current BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (region_code, dataset_version)
);
CREATE INDEX IF NOT EXISTS idx_administrative_regions_geometry
    ON administrative_regions USING GIST (geometry);
CREATE INDEX IF NOT EXISTS idx_administrative_regions_current
    ON administrative_regions (region_code) WHERE is_current;

CREATE TABLE IF NOT EXISTS collection_runs (
    id UUID PRIMARY KEY,
    region_id UUID NOT NULL REFERENCES administrative_regions(id),
    region_dataset_version TEXT NOT NULL,
    mode TEXT NOT NULL CHECK (mode IN ('initial', 'refresh')),
    status TEXT NOT NULL CHECK (status IN (
        'queued', 'running', 'partial', 'completed', 'failed', 'cancelled'
    )),
    requested_sources JSONB NOT NULL,
    config_snapshot JSONB NOT NULL,
    started_at TIMESTAMPTZ,
    finished_at TIMESTAMPTZ,
    checkpoint JSONB NOT NULL DEFAULT '{}'::jsonb,
    metrics JSONB NOT NULL DEFAULT '{}'::jsonb,
    error_summary JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS collection_run_items (
    id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES collection_runs(id) ON DELETE CASCADE,
    source_registry_id UUID NOT NULL REFERENCES source_registry(id),
    source_record_id TEXT NOT NULL,
    item_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'discovered', 'fetched', 'normalized', 'review_required', 'ready', 'rejected'
    )),
    source_url TEXT NOT NULL,
    discovered_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    fetched_at TIMESTAMPTZ,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    next_retry_at TIMESTAMPTZ,
    http_status INTEGER,
    error_code TEXT,
    error_detail TEXT,
    UNIQUE (run_id, item_key)
);
CREATE INDEX IF NOT EXISTS idx_collection_run_items_retry
    ON collection_run_items (run_id, status, next_retry_at);

CREATE TABLE IF NOT EXISTS raw_documents (
    id UUID PRIMARY KEY,
    run_item_id UUID NOT NULL UNIQUE REFERENCES collection_run_items(id) ON DELETE CASCADE,
    canonical_url TEXT NOT NULL,
    content_type TEXT NOT NULL,
    content_hash CHAR(64) NOT NULL,
    body_compressed BYTEA,
    body_encoding TEXT,
    response_headers JSONB NOT NULL DEFAULT '{}'::jsonb,
    retrieved_at TIMESTAMPTZ NOT NULL,
    storage_policy TEXT NOT NULL CHECK (storage_policy IN (
        'full_allowed', 'facts_only', 'metadata_only', 'prohibited'
    )),
    expires_at TIMESTAMPTZ,
    deleted_at TIMESTAMPTZ,
    deletion_reason TEXT,
    CHECK (storage_policy = 'full_allowed' OR body_compressed IS NULL)
);
CREATE INDEX IF NOT EXISTS idx_raw_documents_hash ON raw_documents (content_hash);

CREATE TABLE IF NOT EXISTS spot_candidates (
    id UUID PRIMARY KEY,
    region_id UUID NOT NULL REFERENCES administrative_regions(id),
    stable_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN (
        'draft', 'ready', 'review_required', 'rejected', 'superseded'
    )),
    display_name TEXT,
    location GEOGRAPHY(Point, 4326),
    address_text TEXT,
    normalized_name TEXT,
    source_count INTEGER NOT NULL DEFAULT 0 CHECK (source_count >= 0),
    quality_score NUMERIC(5,2) NOT NULL DEFAULT 0 CHECK (
        quality_score >= 0 AND quality_score <= 100
    ),
    not_seen_since TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (region_id, stable_key)
);
CREATE INDEX IF NOT EXISTS idx_spot_candidates_location
    ON spot_candidates USING GIST (location);
CREATE INDEX IF NOT EXISTS idx_spot_candidates_name_trgm
    ON spot_candidates USING GIN (normalized_name gin_trgm_ops);

CREATE TABLE IF NOT EXISTS field_observations (
    id UUID PRIMARY KEY,
    candidate_id UUID NOT NULL REFERENCES spot_candidates(id) ON DELETE CASCADE,
    run_item_id UUID NOT NULL REFERENCES collection_run_items(id) ON DELETE CASCADE,
    field_name TEXT NOT NULL,
    value JSONB NOT NULL,
    raw_label TEXT,
    extraction_method TEXT NOT NULL CHECK (extraction_method IN (
        'source_native', 'rule', 'openai', 'manual'
    )),
    confidence NUMERIC(4,3) NOT NULL CHECK (confidence >= 0 AND confidence <= 1),
    source_url TEXT NOT NULL,
    source_record_id TEXT NOT NULL,
    observed_at TIMESTAMPTZ,
    retrieved_at TIMESTAMPTZ NOT NULL,
    verified_at TIMESTAMPTZ,
    license_status TEXT NOT NULL CHECK (license_status IN (
        'verified', 'restricted', 'unknown', 'prohibited'
    )),
    evidence_excerpt TEXT,
    UNIQUE (candidate_id, run_item_id, field_name, extraction_method)
);
CREATE INDEX IF NOT EXISTS idx_field_observations_candidate
    ON field_observations (candidate_id, field_name);

CREATE TABLE IF NOT EXISTS ai_processing_runs (
    id UUID PRIMARY KEY,
    collection_run_id UUID NOT NULL REFERENCES collection_runs(id) ON DELETE CASCADE,
    raw_document_id UUID REFERENCES raw_documents(id) ON DELETE SET NULL,
    purpose TEXT NOT NULL CHECK (purpose IN ('source_discovery', 'observation_extraction')),
    provider TEXT NOT NULL DEFAULT 'openai' CHECK (provider = 'openai'),
    model TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    response_id TEXT,
    status TEXT NOT NULL CHECK (status IN (
        'queued', 'completed', 'refused', 'incomplete', 'invalid', 'failed'
    )),
    input_hash CHAR(64) NOT NULL,
    input_tokens INTEGER,
    output_tokens INTEGER,
    web_search_calls INTEGER NOT NULL DEFAULT 0,
    estimated_cost_jpy NUMERIC,
    error_code TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS review_tasks (
    id UUID PRIMARY KEY,
    candidate_id UUID NOT NULL REFERENCES spot_candidates(id) ON DELETE CASCADE,
    observation_id UUID REFERENCES field_observations(id) ON DELETE SET NULL,
    reason_code TEXT NOT NULL,
    severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'blocking')),
    old_value JSONB,
    proposed_value JSONB,
    evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL CHECK (status IN (
        'open', 'approved', 'rejected', 'deferred', 'resolved'
    )),
    due_at TIMESTAMPTZ,
    reviewed_by TEXT,
    reviewed_at TIMESTAMPTZ,
    decision_note TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS idx_review_tasks_open_unique
    ON review_tasks (candidate_id, reason_code, COALESCE(observation_id, '00000000-0000-0000-0000-000000000000'::uuid))
    WHERE status = 'open';

