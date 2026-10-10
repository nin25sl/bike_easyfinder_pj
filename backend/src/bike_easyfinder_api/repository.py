from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import Engine, create_engine, text

from .contracts import Coordinate, InteractionBatch
from .recommendation import Spot


class Repository:
    def __init__(self, database_url: str | None = None, *, engine: Engine | None = None) -> None:
        self.engine = engine or create_engine(database_url, pool_pre_ping=True)

    def nearby_spots(self, origin: Coordinate, radius_km: float, limit: int = 100) -> list[Spot]:
        statement = text(
            """
            SELECT s.id, s.name, s.summary,
                   COALESCE(primary_category.category_code, 'tourist_attraction') AS category,
                   COALESCE(tags.values, ARRAY[]::text[]) AS tags,
                   ST_Y(s.location::geometry) AS latitude,
                   ST_X(s.location::geometry) AS longitude,
                   s.suggested_stay_minutes, s.confidence, s.popularity_score,
                   s.verified_at, s.hours_verified_at
            FROM spots s
            LEFT JOIN LATERAL (
                SELECT category_code FROM spot_category_assignments
                WHERE spot_id=s.id ORDER BY is_primary DESC, category_code LIMIT 1
            ) primary_category ON true
            LEFT JOIN LATERAL (
                SELECT array_agg(tag_code ORDER BY tag_code) AS values
                FROM spot_tag_assignments WHERE spot_id=s.id
            ) tags ON true
            WHERE s.publication_status='published'
              AND s.business_status <> 'permanently_closed'
              AND s.verified_at >= now() - interval '180 days'
              AND ST_DWithin(
                    s.location,
                    ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography,
                    :radius_meters
              )
            ORDER BY s.location <-> ST_SetSRID(ST_MakePoint(:longitude, :latitude), 4326)::geography,
                     s.id
            LIMIT :limit
            """
        )
        with self.engine.connect() as connection:
            rows = connection.execute(
                statement,
                {
                    "longitude": origin.longitude,
                    "latitude": origin.latitude,
                    "radius_meters": radius_km * 1000,
                    "limit": limit,
                },
            ).mappings()
            return [
                Spot(
                    id=row["id"],
                    name=row["name"],
                    summary=row["summary"],
                    category=row["category"],
                    tags=tuple(row["tags"]),
                    coordinate=Coordinate(latitude=row["latitude"], longitude=row["longitude"]),
                    stay_minutes=row["suggested_stay_minutes"],
                    confidence=float(row["confidence"]),
                    popularity_score=float(row["popularity_score"]),
                    verified_at=row["verified_at"],
                    hours_verified_at=row["hours_verified_at"],
                )
                for row in rows
            ]

    def record_interactions(self, installation_id: UUID, token_hash: str, batch: InteractionBatch) -> int:
        if len(token_hash) != 64 or any(character not in "0123456789abcdefABCDEF" for character in token_hash):
            raise ValueError("invalid deletion token hash")
        with self.engine.begin() as connection:
            installation_hash = hashlib.sha256(str(installation_id).encode()).hexdigest()
            tombstoned = connection.execute(
                text(
                    "SELECT 1 FROM deletion_tombstones WHERE installation_id_hash=:hash AND expires_at > now()"
                ),
                {"hash": installation_hash},
            ).first()
            if tombstoned:
                raise PermissionError("installation was deleted")
            existing = connection.execute(
                text("SELECT deletion_token_hash, deleted_at FROM installations WHERE id=:id FOR UPDATE"),
                {"id": installation_id},
            ).mappings().first()
            if existing and (existing["deleted_at"] is not None or existing["deletion_token_hash"] != token_hash.lower()):
                raise PermissionError("installation credentials do not match")
            connection.execute(
                text(
                    """
                    INSERT INTO installations(id, deletion_token_hash, consented_at, last_seen_at)
                    VALUES (:id, :token_hash, now(), now())
                    ON CONFLICT (id) DO UPDATE SET last_seen_at=now()
                    """
                ),
                {"id": installation_id, "token_hash": token_hash.lower()},
            )
            accepted = 0
            for event in batch.events:
                result = connection.execute(
                    text(
                        """
                        INSERT INTO interaction_events(
                            event_id, installation_id, session_id, recommendation_id, spot_id,
                            event_type, occurred_at, rank, available_minutes, interests
                        ) VALUES (
                            :event_id, :installation_id, :session_id, :recommendation_id, :spot_id,
                            :event_type, :occurred_at, :rank, :available_minutes, CAST(:interests AS jsonb)
                        ) ON CONFLICT (event_id) DO NOTHING
                        """
                    ),
                    {
                        "event_id": event.event_id,
                        "installation_id": installation_id,
                        "session_id": event.session_id,
                        "recommendation_id": event.recommendation_id,
                        "spot_id": event.spot_id,
                        "event_type": event.event_type,
                        "occurred_at": event.occurred_at,
                        "rank": event.rank,
                        "available_minutes": event.available_minutes,
                        "interests": json.dumps([item.value for item in event.interests]),
                    },
                )
                accepted += result.rowcount
            return accepted

    def request_deletion(self, installation_id: UUID, raw_token: str) -> None:
        supplied_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        with self.engine.begin() as connection:
            match = connection.execute(
                text(
                    "SELECT 1 FROM installations WHERE id=:id AND deletion_token_hash=:hash AND deleted_at IS NULL"
                ),
                {"id": installation_id, "hash": supplied_hash},
            ).first()
            if match:
                connection.execute(
                    text(
                        """
                        INSERT INTO data_deletion_requests(installation_id)
                        SELECT :id WHERE NOT EXISTS (
                            SELECT 1 FROM data_deletion_requests
                            WHERE installation_id=:id AND status='accepted'
                        )
                        """
                    ),
                    {"id": installation_id},
                )

    def privacy_maintenance_preview(self) -> dict[str, int]:
        with self.engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT
                      (SELECT count(*) FROM data_deletion_requests WHERE status='accepted') AS pending_deletions,
                      (SELECT count(*) FROM interaction_events WHERE created_at < now() - interval '90 days') AS expiring_events,
                      (SELECT count(*) FROM installations i
                       WHERE i.last_seen_at < now() - interval '90 days'
                         AND NOT EXISTS (
                           SELECT 1 FROM interaction_events e WHERE e.installation_id=i.id
                         )) AS expiring_installations,
                      (SELECT count(*) FROM deletion_tombstones WHERE expires_at < now()) AS expiring_tombstones,
                      (SELECT count(*) FROM route_estimate_cache WHERE expires_at < now()) AS expiring_route_cache
                    """
                )
            ).mappings().one()
        return {key: int(value) for key, value in row.items()}

    def execute_deletions_and_retention(self) -> dict[str, int]:
        with self.engine.begin() as connection:
            aggregated = connection.execute(
                text(
                    """
                    INSERT INTO daily_kpis(day, metric_name, dimension, value, distinct_installations)
                    SELECT occurred_at::date, 'interaction_events',
                           jsonb_build_object('event_type', event_type), count(*),
                           count(DISTINCT installation_id)
                    FROM interaction_events
                    WHERE occurred_at::date = current_date - 1
                    GROUP BY occurred_at::date, event_type
                    HAVING count(DISTINCT installation_id) >= 5
                    ON CONFLICT (day, metric_name, dimension) DO UPDATE SET
                        value=EXCLUDED.value,
                        distinct_installations=EXCLUDED.distinct_installations,
                        created_at=now()
                    """
                )
            ).rowcount
            pending = connection.execute(
                text("SELECT id, installation_id FROM data_deletion_requests WHERE status='accepted' FOR UPDATE")
            ).mappings().all()
            for item in pending:
                installation_hash = hashlib.sha256(str(item["installation_id"]).encode()).hexdigest()
                connection.execute(
                    text("DELETE FROM interaction_events WHERE installation_id=:id"),
                    {"id": item["installation_id"]},
                )
                connection.execute(text("DELETE FROM installations WHERE id=:id"), {"id": item["installation_id"]})
                connection.execute(
                    text(
                        """
                        INSERT INTO deletion_tombstones(installation_id_hash, deleted_at, expires_at)
                        VALUES (:hash, now(), now() + interval '35 days')
                        ON CONFLICT (installation_id_hash) DO UPDATE
                        SET deleted_at=now(), expires_at=EXCLUDED.expires_at
                        """
                    ),
                    {"hash": installation_hash},
                )
                connection.execute(
                    text("UPDATE data_deletion_requests SET status='completed', completed_at=now() WHERE id=:id"),
                    {"id": item["id"]},
                )
            expired_events = connection.execute(
                text("DELETE FROM interaction_events WHERE created_at < now() - interval '90 days'")
            ).rowcount
            expired_installations = connection.execute(
                text(
                    """
                    DELETE FROM installations i
                    WHERE i.last_seen_at < now() - interval '90 days'
                      AND NOT EXISTS (SELECT 1 FROM interaction_events e WHERE e.installation_id=i.id)
                    """
                )
            ).rowcount
            connection.execute(text("DELETE FROM daily_kpis WHERE day < current_date - interval '13 months'"))
            connection.execute(text("DELETE FROM deletion_tombstones WHERE expires_at < now()"))
            connection.execute(text("DELETE FROM route_estimate_cache WHERE expires_at < now()"))
        return {
            "deletions_completed": len(pending),
            "kpis_aggregated": aggregated,
            "events_expired": expired_events,
            "installations_expired": expired_installations,
        }
