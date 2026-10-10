from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import Engine, text

CATEGORY_MAP = {
    "tourism=viewpoint": "scenic_view",
    "tourism=attraction": "tourist_attraction",
    "tourism=museum": "historic_site",
    "historic=memorial": "historic_site",
    "historic=archaeological_site": "historic_site",
    "historic=castle": "historic_site",
    "historic=monument": "historic_site",
    "amenity=cafe": "cafe",
    "amenity=restaurant": "restaurant",
    "amenity=fast_food": "restaurant",
    "amenity=public_bath": "onsen",
    "natural=hot_spring": "onsen",
    "hot springs": "onsen",
    "natural=peak": "mountain",
    "mountains": "mountain",
    "natural=beach": "coast",
    "natural=cape": "coast",
    "coasts": "coast",
    "scenic viewpoints": "scenic_view",
    "restaurants": "restaurant",
    "historic sites": "historic_site",
}

TAG_MAP = {
    "tourism=viewpoint": "scenic",
    "tourism=attraction": "scenic",
    "amenity=cafe": "cafe",
    "amenity=restaurant": "food",
    "amenity=fast_food": "food",
    "amenity=public_bath": "onsen",
    "natural=hot_spring": "onsen",
    "hot springs": "onsen",
    "natural=peak": "mountain",
    "mountains": "mountain",
    "natural=beach": "sea",
    "natural=cape": "sea",
    "coasts": "sea",
    "scenic viewpoints": "scenic",
    "restaurants": "food",
    "historic sites": "historic",
    "tourism=museum": "historic",
    "historic=memorial": "historic",
    "historic=archaeological_site": "historic",
    "historic=castle": "historic",
    "historic=monument": "historic",
}


@dataclass(frozen=True)
class PromotionResult:
    promoted: int
    review_required: int


def _flatten(value: object) -> list[str]:
    if isinstance(value, list):
        return [str(item).lower() for item in value]
    if isinstance(value, dict):
        return [str(item).lower() for item in value.values()]
    return [str(value).lower()] if value is not None else []


def _summary(value: object) -> str | None:
    if isinstance(value, list):
        return " / ".join(str(item) for item in value[:3]) or None
    if isinstance(value, str):
        return value
    return None


def promote_ready_candidates(engine: Engine, prefecture_codes: list[str], data_version: str) -> PromotionResult:
    query = text(
        """
        SELECT e.id, e.entity_key, e.region_id, e.representative_candidate_id,
               e.quality_score, e.updated_at,
               representative.display_name, representative.address_text,
               ST_Y(representative.location::geometry) latitude,
               ST_X(representative.location::geometry) longitude,
               jsonb_object_agg(selected.field_name, selected.value)
                   FILTER (WHERE selected.field_name IS NOT NULL) observations
        FROM resolved_spot_entities e
        JOIN administrative_regions r ON r.id=e.region_id
        LEFT JOIN spot_candidates representative ON representative.id=e.representative_candidate_id
        LEFT JOIN LATERAL (
            SELECT fs.field_name, o.value
            FROM entity_field_selections fs
            JOIN field_observations o ON o.id=fs.observation_id
            WHERE fs.entity_id=e.id AND o.license_status <> 'prohibited'
        ) selected ON true
        WHERE e.status='ready' AND e.merged_into_entity_id IS NULL
          AND r.prefecture_code = ANY(:prefecture_codes)
        GROUP BY e.id, representative.id
        ORDER BY e.id
        """
    )
    promoted = review_required = 0
    with engine.begin() as connection:
        # Promotion is a synchronization boundary for the requested regions.
        # Keep historical rows for referential integrity, but remove stale or
        # superseded entities from the published set before upserting ready ones.
        connection.execute(
            text(
                """
                UPDATE spots s SET publication_status='retired', updated_at=now()
                FROM administrative_regions r
                WHERE r.id=s.region_id
                  AND r.prefecture_code = ANY(:prefecture_codes)
                  AND (
                    s.resolved_entity_id IS NULL OR NOT EXISTS (
                        SELECT 1 FROM resolved_spot_entities e
                        WHERE e.id=s.resolved_entity_id
                          AND e.status='ready'
                          AND e.merged_into_entity_id IS NULL
                    )
                  )
                """
            ),
            {"prefecture_codes": prefecture_codes},
        )
        rows = connection.execute(query, {"prefecture_codes": prefecture_codes}).mappings().all()
        for row in rows:
            observations = row["observations"] or {}
            name = observations.get("name") or row["display_name"]
            selected_location = observations.get("location") or {}
            latitude = selected_location.get("latitude") if isinstance(selected_location, dict) else None
            longitude = selected_location.get("longitude") if isinstance(selected_location, dict) else None
            latitude = latitude if latitude is not None else row["latitude"]
            longitude = longitude if longitude is not None else row["longitude"]
            if not name or latitude is None or longitude is None:
                connection.execute(
                    text(
                        """
                        INSERT INTO data_review_tasks(candidate_id, reason_code, severity, evidence)
                        SELECT :id, 'CANONICAL_REQUIRED_FIELD_MISSING', 'blocking', CAST(:evidence AS jsonb)
                        WHERE NOT EXISTS (
                            SELECT 1 FROM data_review_tasks
                            WHERE candidate_id=:id AND reason_code='CANONICAL_REQUIRED_FIELD_MISSING' AND status='open'
                        )
                        """
                    ),
                    {"id": row["representative_candidate_id"], "evidence": json.dumps({"name": bool(name), "location": False})},
                )
                review_required += 1
                continue

            source_values = _flatten(observations.get("source_categories"))
            category = next((CATEGORY_MAP[value] for value in source_values if value in CATEGORY_MAP), "tourist_attraction")
            tags = {TAG_MAP[value] for value in source_values if value in TAG_MAP}
            features = _flatten(observations.get("features"))
            if any("sea" in value or "coast" in value for value in features):
                tags.add("sea")
            stay = observations.get("suggested_stay_minutes") or 30
            try:
                stay = max(0, min(600, int(stay)))
            except (TypeError, ValueError):
                stay = 30

            spot_id = connection.execute(
                text(
                    """
                    INSERT INTO spots(
                        candidate_id, resolved_entity_id, canonical_key, region_id, publication_status, name, summary, location,
                        address_text, business_status, parking_status, motorcycle_access,
                        road_access, suggested_stay_minutes, confidence, verified_at,
                        business_verified_at, data_version, published_at
                    ) VALUES (
                        :candidate_id, :entity_id, :canonical_key, :region_id, 'published', :name, :summary,
                        ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography,
                        :address, :business_status, :parking, :motorcycle_access,
                        :road_access, :stay, :confidence, :verified_at,
                        :verified_at, :data_version, now()
                    ) ON CONFLICT (canonical_key) DO UPDATE SET
                        candidate_id=EXCLUDED.candidate_id, resolved_entity_id=EXCLUDED.resolved_entity_id,
                        region_id=EXCLUDED.region_id,
                        name=EXCLUDED.name, summary=EXCLUDED.summary, location=EXCLUDED.location,
                        address_text=EXCLUDED.address_text, business_status=EXCLUDED.business_status,
                        parking_status=EXCLUDED.parking_status, motorcycle_access=EXCLUDED.motorcycle_access,
                        road_access=EXCLUDED.road_access, suggested_stay_minutes=EXCLUDED.suggested_stay_minutes,
                        confidence=EXCLUDED.confidence, verified_at=EXCLUDED.verified_at,
                        data_version=EXCLUDED.data_version, publication_status='published',
                        published_at=COALESCE(spots.published_at, now()), updated_at=now()
                    RETURNING id
                    """
                ),
                {
                    "candidate_id": row["representative_candidate_id"],
                    "entity_id": row["id"],
                    "canonical_key": row["entity_key"],
                    "region_id": row["region_id"],
                    "name": str(name),
                    "summary": _summary(observations.get("description_facts")),
                    "longitude": longitude,
                    "latitude": latitude,
                    "address": observations.get("address") or row["address_text"],
                    "business_status": observations.get("business_status") or "unknown",
                    "parking": observations.get("parking") or "unknown",
                    "motorcycle_access": observations.get("motorcycle_access") or "unknown",
                    "road_access": observations.get("road_access") or "unknown",
                    "stay": stay,
                    "confidence": min(1, float(row["quality_score"]) / 100),
                    "verified_at": row["updated_at"],
                    "data_version": data_version,
                },
            ).scalar_one()
            _replace_provenance(connection, spot_id, row["id"])
            connection.execute(
                text("DELETE FROM spot_category_assignments WHERE spot_id=:spot_id"),
                {"spot_id": spot_id},
            )
            connection.execute(
                text("DELETE FROM spot_tag_assignments WHERE spot_id=:spot_id"),
                {"spot_id": spot_id},
            )
            connection.execute(
                text(
                    """
                    INSERT INTO spot_category_assignments(spot_id, category_code, is_primary)
                    VALUES (:spot_id, :category, true)
                    ON CONFLICT (spot_id, category_code) DO UPDATE SET is_primary=true
                    """
                ),
                {"spot_id": spot_id, "category": category},
            )
            for tag in tags:
                connection.execute(
                    text(
                        "INSERT INTO spot_tag_assignments(spot_id, tag_code) VALUES (:spot_id, :tag) ON CONFLICT DO NOTHING"
                    ),
                    {"spot_id": spot_id, "tag": tag},
                )
            promoted += 1
    return PromotionResult(promoted, review_required)


def _replace_provenance(connection, spot_id, entity_id) -> None:
    connection.execute(text("DELETE FROM spot_sources WHERE spot_id=:spot_id"), {"spot_id": spot_id})
    sources = connection.execute(text(
        """
        SELECT DISTINCT ON (s.source_key, o.source_record_id)
               s.source_key, s.source_type, o.source_record_id, o.source_url,
               o.retrieved_at, o.verified_at, o.license_status, o.confidence::float
        FROM spot_entity_memberships m
        JOIN field_observations o ON o.candidate_id=m.candidate_id
        JOIN collection_run_items i ON i.id=o.run_item_id
        JOIN source_registry s ON s.id=i.source_registry_id
        WHERE m.entity_id=:entity_id
        ORDER BY s.source_key, o.source_record_id, o.retrieved_at DESC, o.confidence DESC
        """
    ), {"entity_id": entity_id}).mappings().all()
    source_ids = {}
    for source in sources:
        source_id = connection.execute(text(
            """
            INSERT INTO spot_sources(
                spot_id, source_name, source_type, source_record_id, source_url,
                retrieved_at, verified_at, verification_status, license_status, confidence
            ) VALUES (
                :spot_id, :source_key, :source_type, :record_id, :url,
                :retrieved_at, :verified_at, :verification_status, :license_status, :confidence
            ) RETURNING id
            """
        ), {
            "spot_id": spot_id, "source_key": source["source_key"], "source_type": source["source_type"],
            "record_id": source["source_record_id"], "url": source["source_url"],
            "retrieved_at": source["retrieved_at"], "verified_at": source["verified_at"],
            "verification_status": "verified" if source["verified_at"] else "unverified",
            "license_status": source["license_status"], "confidence": source["confidence"],
        }).scalar_one()
        source_ids[(source["source_key"], source["source_record_id"])] = source_id

    selected = connection.execute(text(
        """
        SELECT fs.field_name, fs.rule_version, fs.selection_reason, fs.selected_at,
               o.source_record_id, o.confidence::float, o.verified_at, s.source_key
        FROM entity_field_selections fs
        JOIN field_observations o ON o.id=fs.observation_id
        JOIN collection_run_items i ON i.id=o.run_item_id
        JOIN source_registry s ON s.id=i.source_registry_id
        WHERE fs.entity_id=:entity_id
        """
    ), {"entity_id": entity_id}).mappings().all()
    for field in selected:
        source_id = source_ids.get((field["source_key"], field["source_record_id"]))
        if source_id is None:
            continue
        connection.execute(text(
            """
            INSERT INTO spot_field_sources(
                spot_id, field_name, source_id, confidence, verified_at,
                rule_version, selection_reason, adopted_at, is_adopted
            ) VALUES (
                :spot_id, :field_name, :source_id, :confidence, :verified_at,
                :rule_version, CAST(:selection_reason AS jsonb), :adopted_at, true
            ) ON CONFLICT (spot_id, field_name) WHERE is_adopted DO UPDATE SET
                source_id=EXCLUDED.source_id, confidence=EXCLUDED.confidence,
                verified_at=EXCLUDED.verified_at, rule_version=EXCLUDED.rule_version,
                selection_reason=EXCLUDED.selection_reason, adopted_at=EXCLUDED.adopted_at
            """
        ), {
            "spot_id": spot_id, "field_name": field["field_name"], "source_id": source_id,
            "confidence": field["confidence"], "verified_at": field["verified_at"],
            "rule_version": field["rule_version"], "selection_reason": json.dumps(field["selection_reason"]),
            "adopted_at": field["selected_at"],
        })
