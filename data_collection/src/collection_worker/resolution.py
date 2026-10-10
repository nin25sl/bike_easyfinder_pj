from __future__ import annotations

import json
import uuid
from collections import defaultdict
from typing import Any

from sqlalchemy import Engine, text

from collection_worker.config import Settings
from collection_worker.errors import PolicyError
from collection_worker.repository import Repository
from collection_worker.utils import canonicalize_url


def _score(row: dict[str, Any]) -> tuple[int, dict[str, Any]]:
    similarity = float(row.get("name_similarity") or 0)
    distance = float(row["distance_m"]) if row.get("distance_m") is not None else None
    score = 40 if similarity >= 0.9 else (30 if similarity >= 0.8 else 0)
    if distance is not None:
        score += 30 if distance <= 50 else (20 if distance <= 100 else (10 if distance <= 250 else 0))
    address_match = bool(row.get("address_match"))
    url_match = bool(row.get("url_match"))
    category_match = bool(row.get("category_match"))
    score += 15 if address_match else 0
    score += 10 if url_match else 0
    score += 5 if category_match else 0
    return score, {
        "name_similarity": similarity,
        "distance_m": distance,
        "address_match": address_match,
        "official_url_match": url_match,
        "category_match": category_match,
    }


def _decision(score: int, same_source: bool, distance_m: float | None) -> str:
    if score >= 75 and not same_source and not (distance_m is not None and distance_m > 250):
        return "merge"
    if score >= 55 or same_source:
        return "review"
    return "separate"


def resolve_entities(engine: Engine, repository: Repository, region_id: str, settings: Settings) -> dict[str, int]:
    rule = settings.collection.entity_resolution_rule_version
    _ensure_seed_entities(engine, region_id, rule)
    rows = _candidate_pairs(engine, region_id)
    ambiguous = merged = compared = 0
    for row in rows:
        compared += 1
        left_url = _safe_canonical_url(row.get("left_official_url"))
        right_url = _safe_canonical_url(row.get("right_official_url"))
        distance = float(row["distance_m"]) if row.get("distance_m") is not None else None
        values = {
            "name_similarity": row.get("name_similarity"),
            "distance_m": distance,
            "address_match": bool(
                row.get("left_address") and row.get("left_address") == row.get("right_address")
            ),
            "url_match": bool(left_url and left_url == right_url),
            "category_match": bool(
                set(row.get("left_categories") or []) & set(row.get("right_categories") or [])
            ),
        }
        score, evidence = _score(values)
        evidence.update(
            {
                "left_candidate_id": row["left_id"],
                "right_candidate_id": row["right_id"],
                "score": score,
            }
        )
        same_source = bool(
            row.get("left_source_key")
            and row.get("left_source_key") == row.get("right_source_key")
        )
        decision = _decision(score, same_source, distance)
        if decision == "merge":
            if _merge_entities(engine, row["left_id"], row["right_id"], score, evidence, rule):
                merged += 1
        elif decision == "review":
            entity_id = _entity_for_candidate(engine, row["left_id"])
            repository.add_entity_review(
                entity_id,
                "DUPLICATE_SUSPECTED" if same_source else "ENTITY_MATCH_AMBIGUOUS",
                "medium",
                evidence,
            )
            ambiguous += 1
    _refresh_entity_statuses(engine, region_id)
    return {"compared": compared, "merged": merged, "ambiguous": ambiguous, "entities": _entity_count(engine, region_id)}


def select_entity_fields(engine: Engine, repository: Repository, region_id: str, settings: Settings) -> dict[str, int]:
    rule = settings.collection.field_selection_rule_version
    with engine.connect() as connection:
        observations = connection.execute(text(
            """
            SELECT m.entity_id::text, o.id::text, o.field_name, o.value,
                   o.confidence::float, o.verified_at, o.retrieved_at,
                   o.license_status, s.source_type, s.source_key
            FROM resolved_spot_entities e
            JOIN spot_entity_memberships m ON m.entity_id=e.id
            JOIN field_observations o ON o.candidate_id=m.candidate_id
            JOIN collection_run_items i ON i.id=o.run_item_id
            JOIN source_registry s ON s.id=i.source_registry_id
            WHERE e.region_id=:region_id AND e.merged_into_entity_id IS NULL
            """
        ), {"region_id": region_id}).mappings().all()
    by_field: dict[tuple[str, str], list[tuple[float, dict]]] = defaultdict(list)
    for item in observations:
        score = _field_score(
            item["field_name"], item["source_type"], item["license_status"], item["confidence"]
        )
        by_field[(item["entity_id"], item["field_name"])].append((score, dict(item)))

    selections: list[dict] = []
    reviews: list[dict] = []
    for (entity_id, field_name), choices in by_field.items():
        choices.sort(
            key=lambda pair: (
                pair[0], pair[1]["verified_at"] or pair[1]["retrieved_at"], pair[1]["id"]
            ),
            reverse=True,
        )
        best_score, best = choices[0]
        selections.append({
            "entity_id": entity_id,
            "field_name": field_name,
            "observation_id": best["id"],
            "score": best_score,
            "rule": rule,
            "reason": json.dumps({
                "source_key": best["source_key"], "source_type": best["source_type"]
            }),
        })
        if (
            len(choices) > 1
            and best_score - choices[1][0] < 10
            and best["value"] != choices[1][1]["value"]
        ):
            reviews.append({
                "id": str(uuid.uuid4()),
                "entity_id": entity_id,
                "reason": "SOURCE_CONFLICT",
                "severity": "high",
                "evidence": json.dumps({
                    "field_name": field_name,
                    "preferred_observation_id": best["id"],
                    "alternative_observation_id": choices[1][1]["id"],
                    "score_difference": best_score - choices[1][0],
                }),
            })

    selection_sql = text(
        """
        INSERT INTO entity_field_selections(
            entity_id, field_name, observation_id, selection_score,
            rule_version, selection_reason, selected_at
        ) VALUES (
            :entity_id, :field_name, :observation_id, :score,
            :rule, CAST(:reason AS jsonb), now()
        ) ON CONFLICT (entity_id, field_name) DO UPDATE SET
            observation_id=EXCLUDED.observation_id,
            selection_score=EXCLUDED.selection_score,
            rule_version=EXCLUDED.rule_version,
            selection_reason=EXCLUDED.selection_reason,
            selected_at=now()
        """
    )
    review_sql = text(
        """
        INSERT INTO review_tasks(id, entity_id, reason_code, severity, evidence, status)
        VALUES (:id, :entity_id, :reason, :severity, CAST(:evidence AS jsonb), 'open')
        ON CONFLICT DO NOTHING
        """
    )
    with engine.begin() as connection:
        for offset in range(0, len(selections), 1000):
            connection.execute(selection_sql, selections[offset:offset + 1000])
        for offset in range(0, len(reviews), 1000):
            connection.execute(review_sql, reviews[offset:offset + 1000])
    _refresh_entity_statuses(engine, region_id)
    return {"selected": len(selections), "conflicts": len(reviews)}


def _field_score(field: str, source_type: str, license_status: str, confidence: float) -> float:
    if field == "location":
        priority = {"osm_pbf": 100, "osm_overpass": 100, "public_open_data": 80, "official_web": 70}
    elif field in {"touring_relevance", "features"}:
        priority = {"touring_media": 100, "official_web": 75, "general_web": 60, "public_open_data": 50}
    else:
        priority = {
            "official_web": 100, "manual_seed": 90, "public_open_data": 80,
            "general_web": 70, "osm_pbf": 60, "osm_overpass": 60,
            "openai_web_discovery": 40, "touring_media": 30,
        }
    license_bonus = {"verified": 20, "restricted": 0, "unknown": -40, "prohibited": -100}[license_status]
    return float(priority.get(source_type, 0) + license_bonus + confidence * 10)


def _ensure_seed_entities(engine: Engine, region_id: str, rule: str) -> None:
    with engine.begin() as connection:
        connection.execute(text(
            """
            INSERT INTO resolved_spot_entities(
                id, region_id, entity_key, representative_candidate_id,
                status, resolution_rule_version
            )
            SELECT gen_random_uuid(), c.region_id, 'entity:' || c.stable_key,
                   c.id, 'draft', :rule
            FROM spot_candidates c LEFT JOIN spot_entity_memberships m ON m.candidate_id=c.id
            WHERE c.region_id=:region_id AND m.candidate_id IS NULL
            ON CONFLICT (entity_key) DO NOTHING
            """
        ), {"region_id": region_id, "rule": rule})
        connection.execute(text(
            """
            INSERT INTO spot_entity_memberships(
                entity_id, candidate_id, match_score, decision, evidence, rule_version
            )
            SELECT e.id, c.id, 100, 'seed', '{}'::jsonb, :rule
            FROM spot_candidates c
            JOIN resolved_spot_entities e ON e.entity_key='entity:' || c.stable_key
            LEFT JOIN spot_entity_memberships m ON m.candidate_id=c.id
            WHERE c.region_id=:region_id AND m.candidate_id IS NULL
            ON CONFLICT (candidate_id) DO NOTHING
            """
        ), {"region_id": region_id, "rule": rule})


def _candidate_pairs(engine: Engine, region_id: str) -> list[dict]:
    with engine.connect() as connection:
        rows = connection.execute(text(
            """
            WITH candidate_data AS (
                SELECT c.id, c.normalized_name, c.location,
                       regexp_replace(lower(COALESCE(c.address_text, '')), '[[:space:]]+', '', 'g') normalized_address,
                       source.source_key,
                       official.official_url,
                       CASE WHEN official.official_url IS NULL THEN NULL ELSE
                           lower(regexp_replace(
                               split_part(split_part(official.official_url, '#', 1), '?', 1), '/+$', ''
                           ))
                       END official_url_key,
                       categories.value categories
                FROM spot_candidates c
                LEFT JOIN LATERAL (
                    SELECT s.source_key FROM field_observations o
                    JOIN collection_run_items i ON i.id=o.run_item_id
                    JOIN source_registry s ON s.id=i.source_registry_id
                    WHERE o.candidate_id=c.id ORDER BY o.retrieved_at DESC LIMIT 1
                ) source ON true
                LEFT JOIN LATERAL (
                    SELECT o.value #>> '{}' official_url FROM field_observations o
                    WHERE o.candidate_id=c.id AND o.field_name='official_url'
                    ORDER BY o.confidence DESC, o.retrieved_at DESC LIMIT 1
                ) official ON true
                LEFT JOIN LATERAL (
                    SELECT o.value FROM field_observations o
                    WHERE o.candidate_id=c.id AND o.field_name='source_categories'
                    ORDER BY o.confidence DESC, o.retrieved_at DESC LIMIT 1
                ) categories ON true
                WHERE c.region_id=:region_id AND c.status <> 'superseded'
            ), spatial_pairs AS (
                SELECT left_row.id left_id, right_row.id right_id
                FROM spot_candidates left_row
                JOIN spot_candidates right_row ON
                    right_row.region_id=left_row.region_id
                    AND left_row.id < right_row.id
                    AND right_row.status <> 'superseded'
                    AND ST_DWithin(left_row.location, right_row.location, 250)
                WHERE left_row.region_id=:region_id
                  AND left_row.status <> 'superseded'
                  AND left_row.normalized_name IS NOT NULL
                  AND right_row.normalized_name IS NOT NULL
                  AND similarity(left_row.normalized_name, right_row.normalized_name) >= 0.8
            ), url_pairs AS (
                SELECT left_row.id left_id, right_row.id right_id
                FROM candidate_data left_row
                JOIN candidate_data right_row ON
                    left_row.id < right_row.id
                    AND left_row.official_url_key IS NOT NULL
                    AND left_row.official_url_key = right_row.official_url_key
            ), pair_ids AS (
                SELECT left_id, right_id FROM spatial_pairs
                UNION
                SELECT left_id, right_id FROM url_pairs
            )
            SELECT left_row.id::text left_id, right_row.id::text right_id,
                   left_row.source_key left_source_key, right_row.source_key right_source_key,
                   left_row.normalized_address left_address, right_row.normalized_address right_address,
                   left_row.official_url left_official_url, right_row.official_url right_official_url,
                   left_row.categories left_categories, right_row.categories right_categories,
                   CASE WHEN left_row.location IS NULL OR right_row.location IS NULL THEN NULL
                        ELSE ST_Distance(left_row.location, right_row.location) END distance_m,
                   CASE WHEN left_row.normalized_name IS NULL OR right_row.normalized_name IS NULL THEN 0
                        ELSE similarity(left_row.normalized_name, right_row.normalized_name) END name_similarity
            FROM pair_ids pairs
            JOIN candidate_data left_row ON left_row.id=pairs.left_id
            JOIN candidate_data right_row ON right_row.id=pairs.right_id
            ORDER BY left_row.id, right_row.id
            """
        ), {"region_id": region_id}).mappings().all()
    return [dict(row) for row in rows]


def _safe_canonical_url(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return canonicalize_url(value)
    except (PolicyError, ValueError):
        return None


def _entity_for_candidate(engine: Engine, candidate_id: str) -> str:
    with engine.connect() as connection:
        return connection.execute(text(
            "SELECT entity_id::text FROM spot_entity_memberships WHERE candidate_id=:id"
        ), {"id": candidate_id}).scalar_one()


def _merge_entities(engine: Engine, left_candidate: str, right_candidate: str, score: int, evidence: dict, rule: str) -> bool:
    left = _entity_for_candidate(engine, left_candidate)
    right = _entity_for_candidate(engine, right_candidate)
    if left == right:
        return False
    with engine.begin() as connection:
        rows = connection.execute(text(
            "SELECT id::text, created_at FROM resolved_spot_entities WHERE id IN (:left,:right) ORDER BY created_at,id"
        ), {"left": left, "right": right}).mappings().all()
        winner, loser = rows[0]["id"], rows[1]["id"]
        connection.execute(text(
            """
            UPDATE spot_entity_memberships SET entity_id=:winner, match_score=GREATEST(match_score,:score),
                decision=CASE WHEN decision='seed' THEN 'auto' ELSE decision END,
                evidence=evidence || CAST(:evidence AS jsonb), rule_version=:rule, updated_at=now()
            WHERE entity_id=:loser
            """
        ), {"winner": winner, "loser": loser, "score": score, "evidence": json.dumps(evidence), "rule": rule})
        connection.execute(text(
            "UPDATE resolved_spot_entities SET status='superseded', merged_into_entity_id=:winner, updated_at=now() WHERE id=:loser"
        ), {"winner": winner, "loser": loser})
    return True


def _refresh_entity_statuses(engine: Engine, region_id: str) -> None:
    with engine.begin() as connection:
        connection.execute(text(
            """
            UPDATE resolved_spot_entities e SET
                status=CASE
                    WHEN EXISTS (SELECT 1 FROM review_tasks rt WHERE rt.entity_id=e.id AND rt.status='open') THEN 'review_required'
                    WHEN stats.any_ready THEN 'ready'
                    WHEN stats.all_rejected THEN 'rejected'
                    ELSE 'review_required' END,
                quality_score=COALESCE(stats.average_quality,0), updated_at=now()
            FROM (
                SELECT m.entity_id, bool_or(c.status='ready') any_ready,
                       bool_and(c.status='rejected') all_rejected,
                       avg(c.quality_score) average_quality
                FROM spot_entity_memberships m JOIN spot_candidates c ON c.id=m.candidate_id
                GROUP BY m.entity_id
            ) stats
            WHERE e.id=stats.entity_id AND e.region_id=:region_id AND e.merged_into_entity_id IS NULL
            """
        ), {"region_id": region_id})


def _entity_count(engine: Engine, region_id: str) -> int:
    with engine.connect() as connection:
        return int(connection.execute(text(
            "SELECT count(*) FROM resolved_spot_entities WHERE region_id=:id AND merged_into_entity_id IS NULL"
        ), {"id": region_id}).scalar_one())
