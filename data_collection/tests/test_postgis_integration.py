from __future__ import annotations

import os
import uuid
from pathlib import Path

import pytest
from collection_worker.config import load_settings
from collection_worker.contracts import DiscoveredRecord, Region
from collection_worker.db import create_db_engine, sync_source_registry
from collection_worker.normalize import normalize_payload
from collection_worker.repository import Repository
from collection_worker.resolution import resolve_entities, select_entity_fields
from sqlalchemy import text

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="set RUN_DB_INTEGRATION=1 against a disposable migrated PostGIS database",
)


def test_idempotent_items_retry_state_and_entity_resolution():
    settings = load_settings(Path("data_collection/config/sources.yaml"))
    engine = create_db_engine(settings)
    sync_source_registry(engine, settings)
    repository = Repository(engine)
    region_id = str(uuid.uuid4())
    region_code = f"9{str(uuid.uuid4().int)[-4:]}"
    n03_id = repository.source("n03")["id"]
    with engine.begin() as connection:
        connection.execute(text(
            """
            INSERT INTO administrative_regions(
                id, region_code, region_kind, name_ja, prefecture_code,
                geometry, dataset_version, valid_from, source_registry_id
            ) VALUES (
                :id, :code, 'municipality', 'integration', '99',
                ST_Multi(ST_GeomFromText('POLYGON((130 33,131 33,131 34,130 34,130 33))',4326)),
                'integration-v1', DATE '2026-01-01', :source_id
            )
            """
        ), {"id": region_id, "code": region_code, "source_id": n03_id})
    region = Region(
        id=region_id,
        region_code=region_code,
        region_kind="municipality",
        name_ja="integration",
        prefecture_code="99",
        parent_region_code=None,
        dataset_version="integration-v1",
        bbox=(130, 33, 131, 34),
    )
    run_id = repository.create_run(region, "initial", ["manual_seed", "osm_pbf"], {
        "config_sha256": "integration",
        "schema_version": "002_resolution_batches",
        "region_dataset_version": "integration-v1",
    })

    retry_record = DiscoveredRecord(
        source_record_id="retry-1",
        source_url="https://example.com/retry-1",
        payload={"name": "retry"},
    )
    manual_source = repository.source("manual_seed")
    retry_id = repository.upsert_item(
        run_id, str(manual_source["id"]), region_id, "manual_seed", retry_record
    )
    assert retry_id == repository.upsert_item(
        run_id, str(manual_source["id"]), region_id, "manual_seed", retry_record
    )
    assert repository.mark_item_retry(retry_id, "HTTP_503", "temporary") == 1
    assert repository.item_state(retry_id)["retry_due"] is False

    candidates = []
    for source_key, record_id, latitude, longitude in (
        ("manual_seed", "manual-spot", 33.50000, 130.40000),
        ("osm_pbf", "node/123", 33.50005, 130.40005),
    ):
        source = repository.source(source_key)
        record = DiscoveredRecord(
            source_record_id=record_id,
            source_url=f"https://example.com/{record_id}",
            payload={
                "name": "統合テスト展望台",
                "address": "福岡県統合市1-1",
                "latitude": latitude,
                "longitude": longitude,
                "source_categories": ["tourism=viewpoint"],
            },
        )
        item_id = repository.upsert_item(
            run_id, str(source["id"]), region_id, settings.sources[source_key].source_type, record
        )
        candidate = normalize_payload(record.payload)
        candidate_id = repository.upsert_candidate(region, source_key, record, candidate)
        for observation in candidate.observations:
            repository.add_observation(
                candidate_id, item_id, record, settings.sources[source_key], observation
            )
        repository.update_item(item_id, "ready")
        candidates.append(candidate_id)

    with engine.begin() as connection:
        connection.execute(text(
            "UPDATE spot_candidates SET status='ready', quality_score=90 WHERE id::text = ANY(:ids)"
        ), {"ids": candidates})
    result = resolve_entities(engine, repository, region_id, settings)
    assert result["merged"] == 1
    assert result["entities"] == 1
    assert select_entity_fields(engine, repository, region_id, settings)["selected"] > 0
    with engine.connect() as connection:
        assert connection.execute(text(
            "SELECT count(*) FROM spot_entity_memberships WHERE candidate_id::text = ANY(:ids)"
        ), {"ids": candidates}).scalar_one() == 2
