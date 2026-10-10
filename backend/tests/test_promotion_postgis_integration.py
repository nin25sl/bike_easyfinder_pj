from __future__ import annotations

import os

import pytest
from bike_easyfinder_api.promotion import promote_ready_candidates
from sqlalchemy import create_engine, text

pytestmark = pytest.mark.skipif(
    os.getenv("RUN_DB_INTEGRATION") != "1",
    reason="set RUN_DB_INTEGRATION=1 against a disposable fully migrated PostGIS database",
)


def test_entity_promotion_preserves_all_and_field_provenance():
    engine = create_engine(os.environ["DATABASE_URL"])
    result = promote_ready_candidates(engine, ["99"], "integration-v1")
    assert result.promoted >= 1
    with engine.connect() as connection:
        rows = connection.execute(text(
            """
            SELECT s.id, s.canonical_key, e.entity_key,
                   count(DISTINCT ss.id) source_count,
                   count(DISTINCT sfs.field_name) field_source_count
            FROM spots s
            JOIN resolved_spot_entities e ON e.id=s.resolved_entity_id
            JOIN administrative_regions r ON r.id=e.region_id
            LEFT JOIN spot_sources ss ON ss.spot_id=s.id
            LEFT JOIN spot_field_sources sfs ON sfs.spot_id=s.id AND sfs.is_adopted
            WHERE r.prefecture_code='99'
            GROUP BY s.id, e.id
            """
        )).mappings().all()
    assert rows
    assert all(row["canonical_key"] == row["entity_key"] for row in rows)
    assert all(row["source_count"] >= 2 for row in rows)
    assert all(row["field_source_count"] > 0 for row in rows)
