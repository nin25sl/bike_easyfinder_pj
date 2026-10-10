"""MVP canonical, routing cache, and privacy-aware analytics schema.

Revision ID: 0001_mvp
Revises:
"""
from alembic import op

revision = "0001_mvp"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        r"""
        CREATE TABLE IF NOT EXISTS taxonomy_versions (
            version TEXT PRIMARY KEY,
            status TEXT NOT NULL CHECK (status IN ('draft', 'current', 'retired')),
            published_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS spot_categories (
            code TEXT PRIMARY KEY,
            label_ja TEXT NOT NULL,
            taxonomy_version TEXT NOT NULL REFERENCES taxonomy_versions(version)
        );

        CREATE TABLE IF NOT EXISTS spot_tags (
            code TEXT PRIMARY KEY,
            label_ja TEXT NOT NULL,
            taxonomy_version TEXT NOT NULL REFERENCES taxonomy_versions(version)
        );

        CREATE TABLE IF NOT EXISTS taxonomy_mappings (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            source_name TEXT NOT NULL,
            source_value TEXT NOT NULL,
            target_kind TEXT NOT NULL CHECK (target_kind IN ('category', 'tag')),
            target_code TEXT NOT NULL,
            taxonomy_version TEXT NOT NULL REFERENCES taxonomy_versions(version),
            UNIQUE (source_name, source_value, target_kind, target_code, taxonomy_version)
        );

        CREATE TABLE IF NOT EXISTS spots (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            candidate_id UUID UNIQUE REFERENCES spot_candidates(id) ON DELETE SET NULL,
            region_id UUID NOT NULL REFERENCES administrative_regions(id),
            publication_status TEXT NOT NULL DEFAULT 'draft'
                CHECK (publication_status IN ('draft', 'published', 'suspended', 'retired')),
            name TEXT NOT NULL,
            summary TEXT,
            location GEOGRAPHY(Point, 4326) NOT NULL,
            address_text TEXT,
            business_status TEXT NOT NULL DEFAULT 'unknown'
                CHECK (business_status IN ('open', 'temporarily_closed', 'permanently_closed', 'unknown')),
            parking_status TEXT NOT NULL DEFAULT 'unknown'
                CHECK (parking_status IN ('available', 'unavailable', 'unknown')),
            motorcycle_access TEXT NOT NULL DEFAULT 'unknown'
                CHECK (motorcycle_access IN ('allowed', 'not_allowed', 'unknown')),
            road_access TEXT NOT NULL DEFAULT 'unknown'
                CHECK (road_access IN ('accessible', 'restricted', 'unknown')),
            suggested_stay_minutes INTEGER NOT NULL DEFAULT 30 CHECK (suggested_stay_minutes BETWEEN 0 AND 600),
            confidence NUMERIC(4,3) NOT NULL DEFAULT 0 CHECK (confidence BETWEEN 0 AND 1),
            popularity_score NUMERIC(4,1) NOT NULL DEFAULT 0 CHECK (popularity_score BETWEEN 0 AND 10),
            verified_at TIMESTAMPTZ NOT NULL,
            business_verified_at TIMESTAMPTZ,
            hours_verified_at TIMESTAMPTZ,
            data_version TEXT NOT NULL,
            published_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_spots_location ON spots USING GIST (location);
        CREATE INDEX IF NOT EXISTS idx_spots_publication ON spots (publication_status, verified_at);

        CREATE TABLE IF NOT EXISTS spot_category_assignments (
            spot_id UUID NOT NULL REFERENCES spots(id) ON DELETE CASCADE,
            category_code TEXT NOT NULL REFERENCES spot_categories(code),
            is_primary BOOLEAN NOT NULL DEFAULT false,
            PRIMARY KEY (spot_id, category_code)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS idx_spot_primary_category
            ON spot_category_assignments (spot_id) WHERE is_primary;

        CREATE TABLE IF NOT EXISTS spot_tag_assignments (
            spot_id UUID NOT NULL REFERENCES spots(id) ON DELETE CASCADE,
            tag_code TEXT NOT NULL REFERENCES spot_tags(code),
            PRIMARY KEY (spot_id, tag_code)
        );

        CREATE TABLE IF NOT EXISTS spot_sources (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            spot_id UUID NOT NULL REFERENCES spots(id) ON DELETE CASCADE,
            source_name TEXT NOT NULL,
            source_record_id TEXT NOT NULL,
            source_url TEXT NOT NULL,
            retrieved_at TIMESTAMPTZ NOT NULL,
            license_status TEXT NOT NULL,
            UNIQUE (spot_id, source_name, source_record_id)
        );

        CREATE TABLE IF NOT EXISTS spot_field_sources (
            spot_id UUID NOT NULL REFERENCES spots(id) ON DELETE CASCADE,
            field_name TEXT NOT NULL,
            source_id UUID NOT NULL REFERENCES spot_sources(id) ON DELETE CASCADE,
            confidence NUMERIC(4,3) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
            verified_at TIMESTAMPTZ,
            PRIMARY KEY (spot_id, field_name, source_id)
        );

        CREATE TABLE IF NOT EXISTS spot_hours (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            spot_id UUID NOT NULL REFERENCES spots(id) ON DELETE CASCADE,
            weekday SMALLINT CHECK (weekday BETWEEN 1 AND 7),
            opens_at TIME,
            closes_at TIME,
            raw_text TEXT,
            verified_at TIMESTAMPTZ,
            CHECK (raw_text IS NOT NULL OR (weekday IS NOT NULL AND opens_at IS NOT NULL AND closes_at IS NOT NULL))
        );

        CREATE TABLE IF NOT EXISTS data_review_tasks (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            spot_id UUID REFERENCES spots(id) ON DELETE CASCADE,
            candidate_id UUID REFERENCES spot_candidates(id) ON DELETE CASCADE,
            reason_code TEXT NOT NULL,
            severity TEXT NOT NULL CHECK (severity IN ('low', 'medium', 'high', 'blocking')),
            status TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open', 'approved', 'rejected', 'resolved')),
            evidence JSONB NOT NULL DEFAULT '{}'::jsonb,
            reviewed_by TEXT,
            reviewed_at TIMESTAMPTZ,
            decision_note TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS route_estimate_cache (
            cache_key CHAR(64) PRIMARY KEY,
            spot_id UUID NOT NULL REFERENCES spots(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            outbound_minutes INTEGER NOT NULL,
            return_minutes INTEGER NOT NULL,
            distance_km NUMERIC(8,2) NOT NULL,
            encoded_polyline TEXT NOT NULL,
            generated_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_route_cache_expiry ON route_estimate_cache (expires_at);

        CREATE TABLE IF NOT EXISTS installations (
            id UUID PRIMARY KEY,
            deletion_token_hash CHAR(64) NOT NULL,
            consented_at TIMESTAMPTZ NOT NULL,
            last_seen_at TIMESTAMPTZ NOT NULL,
            deleted_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );

        CREATE TABLE IF NOT EXISTS interaction_events (
            event_id UUID PRIMARY KEY,
            installation_id UUID NOT NULL REFERENCES installations(id) ON DELETE CASCADE,
            session_id UUID NOT NULL,
            recommendation_id UUID NOT NULL,
            spot_id UUID NOT NULL,
            event_type TEXT NOT NULL CHECK (event_type IN (
                'shown', 'interested', 'not_interested', 'visited', 'selected', 'route_started'
            )),
            occurred_at TIMESTAMPTZ NOT NULL,
            rank SMALLINT CHECK (rank BETWEEN 1 AND 5),
            available_minutes INTEGER,
            interests JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        CREATE INDEX IF NOT EXISTS idx_events_installation ON interaction_events (installation_id, occurred_at);
        CREATE INDEX IF NOT EXISTS idx_events_created_at ON interaction_events (created_at);

        CREATE TABLE IF NOT EXISTS data_deletion_requests (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            installation_id UUID NOT NULL,
            requested_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            status TEXT NOT NULL DEFAULT 'accepted' CHECK (status IN ('accepted', 'completed', 'failed')),
            completed_at TIMESTAMPTZ,
            error_code TEXT
        );

        CREATE TABLE IF NOT EXISTS deletion_tombstones (
            installation_id_hash CHAR(64) PRIMARY KEY,
            deleted_at TIMESTAMPTZ NOT NULL,
            expires_at TIMESTAMPTZ NOT NULL
        );

        CREATE TABLE IF NOT EXISTS daily_kpis (
            day DATE NOT NULL,
            metric_name TEXT NOT NULL,
            dimension JSONB NOT NULL DEFAULT '{}'::jsonb,
            value BIGINT NOT NULL,
            distinct_installations INTEGER NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
            PRIMARY KEY (day, metric_name, dimension),
            CHECK (distinct_installations >= 5)
        );

        INSERT INTO taxonomy_versions(version, status, published_at)
        VALUES ('mvp-1', 'current', now()) ON CONFLICT (version) DO NOTHING;

        INSERT INTO spot_categories(code, label_ja, taxonomy_version) VALUES
            ('scenic_view', '景勝地', 'mvp-1'), ('coast', '海岸', 'mvp-1'),
            ('mountain', '山', 'mvp-1'), ('cafe', 'カフェ', 'mvp-1'),
            ('restaurant', '飲食店', 'mvp-1'), ('onsen', '温泉', 'mvp-1'),
            ('roadside_station', '道の駅', 'mvp-1'), ('historic_site', '史跡', 'mvp-1'),
            ('tourist_attraction', '観光地', 'mvp-1')
        ON CONFLICT (code) DO NOTHING;

        INSERT INTO spot_tags(code, label_ja, taxonomy_version) VALUES
            ('scenic', '絶景', 'mvp-1'), ('sea', '海', 'mvp-1'),
            ('mountain', '山', 'mvp-1'), ('winding', 'ワインディング', 'mvp-1'),
            ('cafe', 'カフェ', 'mvp-1'), ('food', '食事', 'mvp-1'),
            ('onsen', '温泉', 'mvp-1'), ('roadside_station', '道の駅', 'mvp-1'),
            ('night_view', '夜景', 'mvp-1'), ('historic', '歴史', 'mvp-1')
        ON CONFLICT (code) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DROP TABLE IF EXISTS daily_kpis, deletion_tombstones, data_deletion_requests,
            interaction_events, installations, route_estimate_cache, data_review_tasks,
            spot_hours, spot_field_sources, spot_sources, spot_tag_assignments,
            spot_category_assignments, spots, taxonomy_mappings, spot_tags,
            spot_categories, taxonomy_versions CASCADE;
        """
    )

