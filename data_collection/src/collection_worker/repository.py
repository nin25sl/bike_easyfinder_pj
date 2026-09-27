from __future__ import annotations

import gzip
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlsplit

from sqlalchemy import Engine, text

from collection_worker.config import SourceConfig
from collection_worker.contracts import DiscoveredRecord, NormalizedCandidate, ObservationInput, Region
from collection_worker.utils import normalize_name, stable_hash


class Repository:
    def __init__(self, engine: Engine):
        self.engine = engine

    def source(self, source_key: str) -> dict:
        with self.engine.connect() as connection:
            row = connection.execute(
                text("SELECT * FROM source_registry WHERE source_key=:key"), {"key": source_key}
            ).mappings().first()
        if not row:
            raise KeyError(source_key)
        return dict(row)

    def register_pending_domain(self, url: str) -> None:
        domain = (urlsplit(url).hostname or "").lower()
        if not domain:
            return
        source_key = f"web:{domain}"
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO source_registry (
                        id, source_key, source_type, base_url, domain,
                        approval_status, license_status, raw_storage_policy,
                        rate_limit_per_minute, request_timeout_seconds,
                        max_pages_per_run, config
                    ) VALUES (
                        :id, :key, 'official_web', :url, :domain,
                        'pending_review', 'unknown', 'metadata_only', 1, 60, 1, '{}'::jsonb
                    ) ON CONFLICT (source_key) DO NOTHING
                    """
                ),
                {
                    "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"source:{source_key}")),
                    "key": source_key,
                    "url": f"https://{domain}/",
                    "domain": domain,
                },
            )

    def create_run(self, region: Region, mode: str, sources: list[str], snapshot: dict) -> str:
        run_id = str(uuid.uuid4())
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO collection_runs (
                        id, region_id, region_dataset_version, mode, status,
                        requested_sources, config_snapshot, started_at
                    ) VALUES (
                        :id, :region_id, :version, :mode, 'running',
                        CAST(:sources AS jsonb), CAST(:snapshot AS jsonb), now()
                    )
                    """
                ),
                {
                    "id": run_id,
                    "region_id": region.id,
                    "version": region.dataset_version,
                    "mode": mode,
                    "sources": json.dumps(sources),
                    "snapshot": json.dumps(snapshot, ensure_ascii=False, default=str),
                },
            )
        return run_id

    def run(self, run_id: str) -> dict:
        with self.engine.connect() as connection:
            row = connection.execute(
                text("SELECT * FROM collection_runs WHERE id=:id"), {"id": run_id}
            ).mappings().first()
        if not row:
            raise KeyError(run_id)
        return dict(row)

    def region_for_run(self, run_id: str) -> Region:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT r.id::text, r.region_code, r.region_kind, r.name_ja,
                           r.prefecture_code, r.parent_region_code, r.dataset_version,
                           ST_XMin(Box2D(r.geometry)) AS min_x,
                           ST_YMin(Box2D(r.geometry)) AS min_y,
                           ST_XMax(Box2D(r.geometry)) AS max_x,
                           ST_YMax(Box2D(r.geometry)) AS max_y
                    FROM collection_runs cr
                    JOIN administrative_regions r ON r.id=cr.region_id
                    WHERE cr.id=:id
                    """
                ),
                {"id": run_id},
            ).mappings().first()
        if not row:
            raise KeyError(run_id)
        return Region(
            id=row["id"], region_code=row["region_code"], region_kind=row["region_kind"],
            name_ja=row["name_ja"], prefecture_code=row["prefecture_code"],
            parent_region_code=row["parent_region_code"], dataset_version=row["dataset_version"],
            bbox=(row["min_x"], row["min_y"], row["max_x"], row["max_y"]),
        )

    def finish_run(self, run_id: str, status: str, metrics: dict, errors: dict) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE collection_runs
                    SET status=:status, metrics=CAST(:metrics AS jsonb),
                        error_summary=CAST(:errors AS jsonb), finished_at=now()
                    WHERE id=:id
                    """
                ),
                {
                    "id": run_id,
                    "status": status,
                    "metrics": json.dumps(metrics),
                    "errors": json.dumps(errors),
                },
            )

    def reopen_run(self, run_id: str) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text("UPDATE collection_runs SET status='running', finished_at=NULL WHERE id=:id"),
                {"id": run_id},
            )

    def upsert_item(self, run_id: str, source_id: str, region_id: str, source_type: str, record: DiscoveredRecord) -> str:
        item_key = stable_hash(region_id, source_type, record.source_record_id)
        item_id = str(uuid.uuid5(uuid.UUID(run_id), item_key))
        with self.engine.begin() as connection:
            row = connection.execute(
                text(
                    """
                    INSERT INTO collection_run_items (
                        id, run_id, source_registry_id, source_record_id,
                        item_key, status, source_url, http_status
                    ) VALUES (
                        :id, :run_id, :source_id, :record_id,
                        :item_key, 'discovered', :source_url, :http_status
                    ) ON CONFLICT (run_id, item_key) DO UPDATE SET
                        source_url=EXCLUDED.source_url,
                        http_status=EXCLUDED.http_status
                    RETURNING id::text
                    """
                ),
                {
                    "id": item_id,
                    "run_id": run_id,
                    "source_id": source_id,
                    "record_id": record.source_record_id,
                    "item_key": item_key,
                    "source_url": record.source_url,
                    "http_status": record.http_status,
                },
            ).scalar_one()
        return row

    def save_raw(self, item_id: str, record: DiscoveredRecord, source: SourceConfig, retention_days: int) -> str:
        raw = (record.raw_text or json.dumps(record.payload, ensure_ascii=False, sort_keys=True)).encode("utf-8")
        content_hash = stable_hash(raw.decode("utf-8"))
        body = gzip.compress(raw) if source.raw_storage_policy == "full_allowed" else None
        raw_id = str(uuid.uuid5(uuid.UUID(item_id), content_hash))
        headers = {
            key: value for key, value in record.response_headers.items()
            if key.lower() not in {"authorization", "cookie", "set-cookie"}
        }
        expires_at = datetime.now(UTC) + timedelta(days=retention_days) if body else None
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO raw_documents (
                        id, run_item_id, canonical_url, content_type,
                        content_hash, body_compressed, body_encoding,
                        response_headers, retrieved_at, storage_policy, expires_at
                    ) VALUES (
                        :id, :item_id, :url, :content_type, :content_hash,
                        :body, 'utf-8', CAST(:headers AS jsonb), now(), :policy, :expires_at
                    ) ON CONFLICT (run_item_id) DO UPDATE SET
                        canonical_url=EXCLUDED.canonical_url,
                        content_type=EXCLUDED.content_type,
                        content_hash=EXCLUDED.content_hash,
                        body_compressed=EXCLUDED.body_compressed,
                        response_headers=EXCLUDED.response_headers,
                        retrieved_at=now(), storage_policy=EXCLUDED.storage_policy,
                        expires_at=EXCLUDED.expires_at, deleted_at=NULL, deletion_reason=NULL
                    """
                ),
                {
                    "id": raw_id,
                    "item_id": item_id,
                    "url": record.source_url,
                    "content_type": record.content_type,
                    "content_hash": content_hash,
                    "body": body,
                    "headers": json.dumps(headers),
                    "policy": source.raw_storage_policy,
                    "expires_at": expires_at,
                },
            )
        return raw_id

    def upsert_candidate(
        self,
        region: Region,
        source_key: str,
        record: DiscoveredRecord,
        candidate: NormalizedCandidate,
    ) -> str:
        stable_key = stable_hash(source_key, record.source_record_id)
        candidate_id = str(uuid.uuid5(uuid.UUID(region.id), stable_key))
        location_sql = (
            "ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography"
            if candidate.latitude is not None and candidate.longitude is not None
            else "NULL"
        )
        query = text(
            f"""
            INSERT INTO spot_candidates (
                id, region_id, stable_key, status, display_name, location,
                address_text, normalized_name, source_count, updated_at
            ) VALUES (
                :id, :region_id, :stable_key, 'draft', :name, {location_sql},
                :address, :normalized_name, 1, now()
            ) ON CONFLICT (region_id, stable_key) DO UPDATE SET
                display_name=COALESCE(EXCLUDED.display_name, spot_candidates.display_name),
                location=COALESCE(EXCLUDED.location, spot_candidates.location),
                address_text=COALESCE(EXCLUDED.address_text, spot_candidates.address_text),
                normalized_name=COALESCE(EXCLUDED.normalized_name, spot_candidates.normalized_name),
                source_count=GREATEST(spot_candidates.source_count, 1),
                updated_at=now(), not_seen_since=NULL
            RETURNING id::text
            """
        )
        with self.engine.begin() as connection:
            return connection.execute(
                query,
                {
                    "id": candidate_id,
                    "region_id": region.id,
                    "stable_key": stable_key,
                    "name": candidate.name,
                    "latitude": candidate.latitude,
                    "longitude": candidate.longitude,
                    "address": candidate.address,
                    "normalized_name": normalize_name(candidate.name),
                },
            ).scalar_one()

    def add_observation(
        self,
        candidate_id: str,
        item_id: str,
        record: DiscoveredRecord,
        source: SourceConfig,
        observation: ObservationInput,
    ) -> str:
        observation_id = str(
            uuid.uuid5(uuid.UUID(candidate_id), f"{item_id}:{observation.field_name}:{observation.extraction_method}")
        )
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO field_observations (
                        id, candidate_id, run_item_id, field_name, value,
                        raw_label, extraction_method, confidence, source_url,
                        source_record_id, observed_at, retrieved_at,
                        verified_at, license_status, evidence_excerpt
                    ) VALUES (
                        :id, :candidate_id, :item_id, :field_name, CAST(:value AS jsonb),
                        :raw_label, :method, :confidence, :source_url,
                        :source_record_id, :observed_at, now(),
                        CASE WHEN :license_status='verified' THEN now() ELSE NULL END,
                        :license_status, :evidence
                    ) ON CONFLICT (candidate_id, run_item_id, field_name, extraction_method)
                    DO UPDATE SET value=EXCLUDED.value, confidence=EXCLUDED.confidence,
                        retrieved_at=now(), license_status=EXCLUDED.license_status,
                        evidence_excerpt=EXCLUDED.evidence_excerpt
                    """
                ),
                {
                    "id": observation_id,
                    "candidate_id": candidate_id,
                    "item_id": item_id,
                    "field_name": observation.field_name,
                    "value": json.dumps(observation.value, ensure_ascii=False),
                    "raw_label": observation.raw_label,
                    "method": observation.extraction_method,
                    "confidence": observation.confidence,
                    "source_url": record.source_url,
                    "source_record_id": record.source_record_id,
                    "observed_at": observation.observed_at,
                    "license_status": source.license_status,
                    "evidence": observation.evidence_excerpt,
                },
            )
        return observation_id

    def update_item(self, item_id: str, status: str, error_code: str | None = None, error_detail: str | None = None) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    UPDATE collection_run_items SET status=:status,
                        fetched_at=CASE WHEN :status <> 'discovered' THEN COALESCE(fetched_at, now()) ELSE fetched_at END,
                        error_code=:error_code, error_detail=:error_detail,
                        attempt_count=attempt_count + :attempt_increment
                    WHERE id=:id
                    """
                ),
                {
                    "id": item_id,
                    "status": status,
                    "error_code": error_code,
                    "error_detail": error_detail,
                    "attempt_increment": 1 if error_code else 0,
                },
            )

    def add_review(self, candidate_id: str, reason: str, severity: str, evidence: dict | None = None) -> None:
        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO review_tasks (
                        id, candidate_id, reason_code, severity, evidence, status
                    ) VALUES (
                        :id, :candidate_id, :reason, :severity, CAST(:evidence AS jsonb), 'open'
                    ) ON CONFLICT DO NOTHING
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "candidate_id": candidate_id,
                    "reason": reason,
                    "severity": severity,
                    "evidence": json.dumps(evidence or {}),
                },
            )

    def record_ai_run(self, run_id: str, raw_id: str | None, purpose: str, result: Any, prompt_version: str, web_search_calls: int = 0) -> None:
        def value(name: str, default: Any = None) -> Any:
            if isinstance(result, dict):
                return result.get(name, default)
            return getattr(result, name, default)

        with self.engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO ai_processing_runs (
                        id, collection_run_id, raw_document_id, purpose,
                        model, prompt_version, response_id, status, input_hash,
                        input_tokens, output_tokens, web_search_calls, error_code,
                        completed_at
                    ) VALUES (
                        :id, :run_id, :raw_id, :purpose, :model, :prompt_version,
                        :response_id, :status, :input_hash, :input_tokens,
                        :output_tokens, :web_search_calls, :error_code, now()
                    )
                    """
                ),
                {
                    "id": str(uuid.uuid4()),
                    "run_id": run_id,
                    "raw_id": raw_id,
                    "purpose": purpose,
                    "model": value("model", "unknown"),
                    "prompt_version": prompt_version,
                    "response_id": value("response_id"),
                    "status": value("status", "failed"),
                    "input_hash": value("input_hash", "0" * 64),
                    "input_tokens": value("input_tokens"),
                    "output_tokens": value("output_tokens"),
                    "web_search_calls": web_search_calls or value("web_search_calls", 0),
                    "error_code": value("error_code"),
                },
            )
