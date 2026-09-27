from __future__ import annotations

from sqlalchemy import Engine, text

from collection_worker.config import Settings
from collection_worker.repository import Repository


BLOCKING_REASONS = {
    "LICENSE_UNKNOWN",
    "LOCATION_MISSING",
    "OUTSIDE_REGION",
    "AI_ONLY_EVIDENCE",
    "CLOSED_OR_UNAVAILABLE",
}


def assess_candidate(engine: Engine, repository: Repository, candidate_id: str, settings: Settings) -> str:
    with engine.connect() as connection:
        row = connection.execute(
            text(
                """
                SELECT c.display_name, c.address_text, c.location IS NOT NULL AS has_location,
                       CASE WHEN c.location IS NULL THEN NULL
                            ELSE ST_Covers(r.geometry, c.location::geometry) END AS inside,
                       CASE WHEN c.location IS NULL THEN NULL
                            ELSE ST_Distance(r.geometry::geography, c.location) END AS distance_m,
                       bool_and(o.license_status='verified') AS all_licenses_verified,
                       bool_and(o.extraction_method='openai') AS ai_only,
                       bool_or(o.field_name='business_status' AND o.value #>> '{}' IN ('permanently_closed','temporarily_closed')) AS unavailable,
                       count(DISTINCT i.source_registry_id) AS source_count,
                       EXISTS (
                           SELECT 1 FROM field_observations conflict
                           WHERE conflict.candidate_id=c.id
                             AND conflict.field_name NOT IN ('source_payload', 'features', 'source_categories')
                           GROUP BY conflict.field_name
                           HAVING count(DISTINCT conflict.value) > 1
                       ) AS has_conflict
                FROM spot_candidates c
                JOIN administrative_regions r ON r.id=c.region_id
                LEFT JOIN field_observations o ON o.candidate_id=c.id
                LEFT JOIN collection_run_items i ON i.id=o.run_item_id
                WHERE c.id=:id
                GROUP BY c.id, r.id
                """
            ),
            {"id": candidate_id},
        ).mappings().one()

    reasons: list[tuple[str, str]] = []
    if not row["display_name"]:
        reasons.append(("NAME_MISSING", "high"))
    if not row["has_location"] and not row["address_text"]:
        reasons.append(("LOCATION_MISSING", "blocking"))
    if row["has_location"] and not row["inside"]:
        if row["distance_m"] is not None and row["distance_m"] <= settings.collection.outside_region_review_meters:
            reasons.append(("OUTSIDE_REGION", "blocking"))
        else:
            reasons.append(("OUTSIDE_REGION_REJECTED", "blocking"))
    if not row["all_licenses_verified"]:
        reasons.append(("LICENSE_UNKNOWN", "blocking"))
    if row["ai_only"]:
        reasons.append(("AI_ONLY_EVIDENCE", "blocking"))
    if row["unavailable"]:
        reasons.append(("CLOSED_OR_UNAVAILABLE", "blocking"))
    if row["has_conflict"]:
        reasons.append(("SOURCE_CONFLICT", "high"))
    with engine.begin() as connection:
        connection.execute(
            text("UPDATE review_tasks SET status='resolved', reviewed_at=now(), decision_note='Superseded by automatic reassessment' WHERE candidate_id=:id AND status='open' AND reason_code <> 'DUPLICATE_SUSPECTED'"),
            {"id": candidate_id},
        )
    for reason, severity in reasons:
        repository.add_review(candidate_id, reason, severity)

    score = 0.0
    score += 20 if row["display_name"] else 0
    score += 15 if row["has_location"] or row["address_text"] else 0
    score += 25 if row["all_licenses_verified"] else 0
    score += 20 if not row["ai_only"] else 0
    score += min(int(row["source_count"] or 0), 2) * 5
    score += 10 if row["inside"] else 0
    rejected = any(reason == "OUTSIDE_REGION_REJECTED" for reason, _ in reasons)
    status = "rejected" if rejected else ("review_required" if reasons else "ready")
    with engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE spot_candidates SET status=:status, quality_score=:score, source_count=:count, updated_at=now() WHERE id=:id"
            ),
            {"id": candidate_id, "status": status, "score": min(score, 100), "count": int(row["source_count"] or 0)},
        )
    return status


def flag_duplicates(engine: Engine, repository: Repository, region_id: str, settings: Settings) -> int:
    with engine.begin() as connection:
        connection.execute(
            text(
                """
                UPDATE review_tasks rt SET status='resolved', reviewed_at=now(),
                    decision_note='Superseded by automatic duplicate reassessment'
                FROM spot_candidates c
                WHERE rt.candidate_id=c.id AND c.region_id=:region_id
                  AND rt.reason_code='DUPLICATE_SUSPECTED' AND rt.status='open'
                """
            ),
            {"region_id": region_id},
        )
    with engine.connect() as connection:
        pairs = connection.execute(
            text(
                """
                SELECT a.id::text AS left_id, b.id::text AS right_id,
                       ST_Distance(a.location, b.location) AS distance_m,
                       similarity(a.normalized_name, b.normalized_name) AS name_similarity
                FROM spot_candidates a
                JOIN spot_candidates b ON a.region_id=b.region_id AND a.id < b.id
                WHERE a.region_id=:region_id
                  AND a.location IS NOT NULL AND b.location IS NOT NULL
                  AND a.normalized_name IS NOT NULL AND b.normalized_name IS NOT NULL
                  AND ST_DWithin(a.location, b.location, :distance)
                  AND similarity(a.normalized_name, b.normalized_name) >= :similarity
                """
            ),
            {
                "region_id": region_id,
                "distance": settings.collection.duplicate_distance_meters,
                "similarity": settings.collection.duplicate_name_similarity,
            },
        ).mappings().all()
    for pair in pairs:
        evidence = {"other_candidate_id": pair["right_id"], "distance_m": pair["distance_m"], "name_similarity": pair["name_similarity"]}
        repository.add_review(pair["left_id"], "DUPLICATE_SUSPECTED", "medium", evidence)
        repository.add_review(pair["right_id"], "DUPLICATE_SUSPECTED", "medium", {**evidence, "other_candidate_id": pair["left_id"]})
        with engine.begin() as connection:
            connection.execute(
                text("UPDATE spot_candidates SET status='review_required' WHERE id IN (:left_id, :right_id) AND status='ready'"),
                {"left_id": pair["left_id"], "right_id": pair["right_id"]},
            )
    return len(pairs)
