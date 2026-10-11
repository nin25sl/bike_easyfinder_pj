from __future__ import annotations

import hashlib
import html
import io
import json
import math
import re
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable
from urllib.parse import urlencode

import boto3
from PIL import Image, UnidentifiedImageError
from rapidfuzz.fuzz import ratio
from sqlalchemy import Engine, text

from collection_worker.config import Settings
from collection_worker.http import fetch_url
from collection_worker.utils import normalize_name

ALLOWED_LICENSES = {
    "cc0": "CC0",
    "cc0 1.0": "CC0-1.0",
    "public domain": "Public Domain",
    "pd": "Public Domain",
    "pdm": "Public Domain",
    "cc by 1.0": "CC-BY-1.0",
    "cc by 2.0": "CC-BY-2.0",
    "cc by 2.5": "CC-BY-2.5",
    "cc by 3.0": "CC-BY-3.0",
    "cc by 4.0": "CC-BY-4.0",
    "cc by-sa 1.0": "CC-BY-SA-1.0",
    "cc by-sa 2.0": "CC-BY-SA-2.0",
    "cc by-sa 2.5": "CC-BY-SA-2.5",
    "cc by-sa 3.0": "CC-BY-SA-3.0",
    "cc by-sa 4.0": "CC-BY-SA-4.0",
}


def _plain(value: str | None) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", html.unescape(value or ""))).strip()


def accepted_license(short_name: str | None) -> str | None:
    value = _plain(short_name).lower().replace("creative commons", "cc")
    value = re.sub(r"\s+", " ", value).strip()
    for normalized in ALLOWED_LICENSES.values():
        if value == normalized.lower():
            return normalized
    return ALLOWED_LICENSES.get(value)


def _meta(ext: dict[str, Any], key: str) -> str:
    value = ext.get(key, {})
    return str(value.get("value", "")) if isinstance(value, dict) else ""


def _float(value: str) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> int:
    radius = 6_371_000
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


@dataclass(frozen=True)
class MediaCandidate:
    page_id: str
    revision_id: str | None
    title: str
    page_url: str
    original_url: str
    mime_type: str
    width: int
    height: int
    creator: str
    license_name: str
    license_url: str
    attribution: str
    latitude: float | None
    longitude: float | None


def parse_candidate(page: dict[str, Any]) -> MediaCandidate:
    info = (page.get("imageinfo") or [{}])[0]
    ext = info.get("extmetadata") or {}
    title = str(page.get("title", "")).removeprefix("File:")
    creator = _plain(_meta(ext, "Artist") or _meta(ext, "Credit"))
    license_raw = _meta(ext, "LicenseShortName")
    license_name = accepted_license(license_raw) or _plain(license_raw) or "Unknown"
    license_url = _plain(_meta(ext, "LicenseUrl"))
    attribution = _plain(_meta(ext, "Attribution") or creator)
    return MediaCandidate(
        page_id=str(page.get("pageid", "")),
        revision_id=str(page.get("lastrevid")) if page.get("lastrevid") else None,
        title=title,
        page_url=str(info.get("descriptionurl") or f"https://commons.wikimedia.org/wiki/File:{title}"),
        original_url=str(info.get("url", "")),
        mime_type=str(info.get("mime", "")),
        width=int(info.get("width") or 0),
        height=int(info.get("height") or 0),
        creator=creator,
        license_name=license_name,
        license_url=license_url,
        attribution=attribution,
        latitude=_float(_meta(ext, "GPSLatitude")),
        longitude=_float(_meta(ext, "GPSLongitude")),
    )


class WikimediaClient:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.source = settings.sources["wikimedia_commons"]

    def search(self, name: str) -> list[MediaCandidate]:
        params = {
            "action": "query", "format": "json", "formatversion": "2",
            "generator": "search", "gsrnamespace": "6", "gsrsearch": name,
            "gsrlimit": str(self.settings.media.max_candidates),
            "prop": "imageinfo", "iiprop": "url|mime|size|extmetadata|commonmetadata",
        }
        url = f"{self.source.base_url}?{urlencode(params)}"
        result = fetch_url(
            url, allowed_domain="commons.wikimedia.org",
            timeout_seconds=self.source.request_timeout_seconds,
            max_bytes=self.settings.collection.max_response_bytes,
            headers={"User-Agent": str(self.source.config.get("user_agent")), "Accept-Encoding": "gzip"},
            max_retries=self.settings.collection.max_item_attempts,
        )
        payload = json.loads(result.content)
        return [parse_candidate(page) for page in payload.get("query", {}).get("pages", [])]

    def download(self, url: str) -> bytes:
        return fetch_url(
            url, allowed_domain="upload.wikimedia.org",
            timeout_seconds=self.source.request_timeout_seconds,
            max_bytes=self.settings.media.max_original_bytes,
            headers={"User-Agent": str(self.source.config.get("user_agent"))},
            max_retries=self.settings.collection.max_item_attempts,
        ).content


class ObjectStore:
    def __init__(self, settings: Settings):
        endpoint = __import__("os").getenv("MEDIA_ENDPOINT_URL", settings.media.endpoint_url)
        self.bucket = settings.media.bucket
        self.client = boto3.client(
            "s3", endpoint_url=endpoint,
            aws_access_key_id=settings.media_access_key,
            aws_secret_access_key=settings.media_secret_key,
            region_name="us-east-1",
        )

    def ensure_bucket(self) -> None:
        try:
            self.client.head_bucket(Bucket=self.bucket)
        except Exception:
            self.client.create_bucket(Bucket=self.bucket)

    def put(self, key: str, body: bytes, content_type: str, metadata: dict[str, str] | None = None) -> None:
        self.client.put_object(Bucket=self.bucket, Key=key, Body=body, ContentType=content_type, Metadata=metadata or {})

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)


def validate_and_transform(data: bytes, settings: Settings) -> tuple[bytes, str, int, int]:
    Image.MAX_IMAGE_PIXELS = 80_000_000
    try:
        with Image.open(io.BytesIO(data)) as image:
            image.verify()
        with Image.open(io.BytesIO(data)) as image:
            detected_mime = Image.MIME.get(image.format, "application/octet-stream")
            image = image.convert("RGB")
            width, height = image.size
            image.thumbnail((settings.media.derivative_max_edge, settings.media.derivative_max_edge))
            output = io.BytesIO()
            image.save(output, "WEBP", quality=settings.media.webp_quality, method=6)
            return output.getvalue(), detected_mime, width, height
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Downloaded content is not a safe supported image") from exc


def _targets(engine: Engine, statuses: list[str], limit: int | None, ids: list[str] | None = None) -> list[dict]:
    ids = ids or []
    sql = text("""
        WITH targets AS (
          SELECT 'spot' target_kind, s.id target_id, s.name target_name,
                 ST_Y(s.location::geometry) latitude, ST_X(s.location::geometry) longitude, 0 priority
          FROM spots s
          WHERE s.publication_status='published' AND 'published'=ANY(:statuses)
          UNION ALL
          SELECT 'entity', e.id, COALESCE(c.display_name, c.normalized_name),
                 ST_Y(c.location::geometry), ST_X(c.location::geometry),
                 CASE e.status WHEN 'ready' THEN 1 ELSE 2 END
          FROM resolved_spot_entities e
          JOIN spot_candidates c ON c.id=e.representative_candidate_id
          WHERE e.status=ANY(:statuses)
        )
        SELECT t.* FROM targets t
        WHERE (:use_ids=false OR t.target_id::text=ANY(:ids))
          AND NOT EXISTS (
            SELECT 1 FROM spot_media m
            WHERE m.status='ready' AND m.is_primary
              AND ((t.target_kind='spot' AND m.spot_id=t.target_id)
                OR (t.target_kind='entity' AND m.entity_id=t.target_id))
          )
        ORDER BY priority, target_name, target_id
        LIMIT :limit
    """)
    with engine.connect() as connection:
        rows = connection.execute(sql, {
            "statuses": statuses, "use_ids": bool(ids), "ids": ids,
            "limit": limit or 2_147_483_647,
        }).mappings().all()
    return [dict(row) for row in rows]


def _create_run(engine: Engine, source_id: str, statuses: list[str], limit: int | None, dry_run: bool, targets: list[dict]) -> str:
    run_id = str(uuid.uuid4())
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO media_collection_runs(id, source_registry_id, status, target_statuses, target_limit, dry_run)
            VALUES (:id, :source, 'running', CAST(:statuses AS jsonb), :limit, :dry_run)
        """), {"id": run_id, "source": source_id, "statuses": json.dumps(statuses), "limit": limit, "dry_run": dry_run})
        for target in targets:
            connection.execute(text("""
                INSERT INTO media_collection_run_items(
                  id, run_id, target_kind, target_id, target_name, latitude, longitude, status
                ) VALUES (:id, :run, :kind, :target, :name, :lat, :lon, 'pending')
            """), {"id": str(uuid.uuid4()), "run": run_id, "kind": target["target_kind"],
                    "target": target["target_id"], "name": target["target_name"],
                    "lat": target["latitude"], "lon": target["longitude"]})
    return run_id


def _score(target: dict, candidate: MediaCandidate, settings: Settings) -> tuple[float, int | None, bool]:
    name_score = ratio(normalize_name(target["target_name"]), normalize_name(candidate.title)) / 100
    distance = None
    if None not in (target["latitude"], target["longitude"], candidate.latitude, candidate.longitude):
        distance = distance_meters(target["latitude"], target["longitude"], candidate.latitude, candidate.longitude)
    automatic = (
        name_score >= settings.media.min_name_similarity
        and distance is not None
        and distance <= settings.media.auto_match_distance_meters
    )
    score = name_score * 70 + (30 if distance is not None and distance <= settings.media.auto_match_distance_meters else 0)
    return round(score, 2), distance, automatic


def _record_candidate(engine: Engine, source_id: str, item: dict, candidate: MediaCandidate,
                      rank: int, score: float, distance: int | None, status: str,
                      rejection_reason: str | None = None) -> str:
    media_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"commons:{item['target_kind']}:{item['target_id']}:{candidate.page_id}"))
    columns = {"spot_id": item["target_id"] if item["target_kind"] == "spot" else None,
               "entity_id": item["target_id"] if item["target_kind"] == "entity" else None}
    with engine.begin() as connection:
        connection.execute(text("""
            INSERT INTO spot_media(
              id, spot_id, entity_id, source_registry_id, source_page_id, source_revision_id,
              source_page_url, original_url, title, creator, license_status, license_name,
              license_url, attribution_text, verified_at, match_score, distance_meters,
              status, rejection_reason
            ) VALUES (
              :id, :spot_id, :entity_id, :source, :page_id, :revision, :page_url, :original_url,
              :title, :creator, :license_status, :license_name, :license_url, :attribution,
              now(), :score, :distance, :status, :reason
            ) ON CONFLICT (source_registry_id, source_page_id, spot_id, entity_id)
              DO UPDATE SET source_revision_id=EXCLUDED.source_revision_id,
                license_status=EXCLUDED.license_status, license_name=EXCLUDED.license_name,
                license_url=EXCLUDED.license_url, attribution_text=EXCLUDED.attribution_text,
                verified_at=now(), match_score=EXCLUDED.match_score,
                distance_meters=EXCLUDED.distance_meters, status=EXCLUDED.status,
                rejection_reason=EXCLUDED.rejection_reason, updated_at=now()
        """), {"id": media_id, **columns, "source": source_id, "page_id": candidate.page_id,
                "revision": candidate.revision_id, "page_url": candidate.page_url,
                "original_url": candidate.original_url, "title": candidate.title,
                "creator": candidate.creator or "Unknown", "license_status": "verified" if accepted_license(candidate.license_name) else "prohibited",
                "license_name": candidate.license_name, "license_url": candidate.license_url or candidate.page_url,
                "attribution": candidate.attribution or candidate.creator or candidate.title,
                "score": score, "distance": distance, "status": status, "reason": rejection_reason})
        connection.execute(text("""
            INSERT INTO media_collection_candidates(run_item_id, media_id, rank)
            VALUES (:item, :media, :rank) ON CONFLICT DO NOTHING
        """), {"item": item["id"], "media": media_id, "rank": rank})
    return media_id


def _finish_item(engine: Engine, item_id: str, status: str, count: int, error: Exception | None = None) -> None:
    with engine.begin() as connection:
        connection.execute(text("""
            UPDATE media_collection_run_items SET status=:status, candidate_count=:count,
              attempt_count=attempt_count+1, error_code=:code, error_detail=:detail,
              finished_at=now() WHERE id=:id
        """), {"id": item_id, "status": status, "count": count,
                "code": type(error).__name__ if error else None, "detail": str(error)[:500] if error else None})


def _run_items(engine: Engine, run_id: str, failed_only: bool = False) -> list[dict]:
    states = ["failed"] if failed_only else ["pending", "failed"]
    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT * FROM media_collection_run_items WHERE run_id=:run AND status=ANY(:states)
            ORDER BY target_name, id
        """), {"run": run_id, "states": states}).mappings().all()
    return [dict(row) for row in rows]


def _finalize(engine: Engine, run_id: str) -> dict:
    with engine.begin() as connection:
        counts = dict(connection.execute(text("""
            SELECT status, count(*)::int FROM media_collection_run_items
            WHERE run_id=:run GROUP BY status
        """), {"run": run_id}).all())
        total_bytes = connection.execute(text("""
            SELECT COALESCE(sum(m.byte_size),0)::bigint FROM spot_media m
            JOIN media_collection_candidates c ON c.media_id=m.id
            JOIN media_collection_run_items i ON i.id=c.run_item_id WHERE i.run_id=:run
        """), {"run": run_id}).scalar_one()
        metrics = {"processed": sum(counts.values()), "status_counts": counts, "stored_bytes": int(total_bytes)}
        status = "partial" if counts.get("failed", 0) else "completed"
        connection.execute(text("""
            UPDATE media_collection_runs SET status=:status, metrics=CAST(:metrics AS jsonb),
              finished_at=now() WHERE id=:run
        """), {"run": run_id, "status": status, "metrics": json.dumps(metrics)})
    return {"run_id": run_id, "status": status, **metrics}


def _process(engine: Engine, settings: Settings, run_id: str, client: WikimediaClient,
             store: ObjectStore, failed_only: bool = False) -> dict:
    source_id = str(_source(engine)["id"])
    store.ensure_bucket()
    for item in _run_items(engine, run_id, failed_only):
        try:
            with engine.begin() as connection:
                connection.execute(text("UPDATE media_collection_run_items SET status='searching', started_at=now() WHERE id=:id"), {"id": item["id"]})
            candidates = client.search(item["target_name"])
            selected: tuple[str, MediaCandidate] | None = None
            for rank, candidate in enumerate(candidates, 1):
                score, distance, automatic = _score(item, candidate, settings)
                license_ok = bool(accepted_license(candidate.license_name) and candidate.creator and candidate.license_url and candidate.original_url)
                status = "ready" if automatic and license_ok and selected is None else "review_required"
                reason = None
                if not license_ok:
                    status, reason = "rejected", "LICENSE_OR_ATTRIBUTION_NOT_ALLOWED"
                media_id = _record_candidate(engine, source_id, item, candidate, rank, score, distance, status, reason)
                if status == "ready":
                    selected = media_id, candidate
            if selected:
                media_id, candidate = selected
                original = client.download(candidate.original_url)
                derivative, detected_mime, width, height = validate_and_transform(original, settings)
                digest = hashlib.sha256(original).hexdigest()
                extension = (candidate.original_url.rsplit(".", 1)[-1].split("?", 1)[0][:8] or "bin").lower()
                original_key = f"original/{digest}.{extension}"
                derivative_key = f"derived/{digest}-1600.webp"
                store.put(original_key, original, candidate.mime_type or detected_mime, {"sha256": digest})
                store.put(derivative_key, derivative, "image/webp", {"source-sha256": digest})
                with engine.begin() as connection:
                    connection.execute(text("""
                        UPDATE spot_media SET original_object_key=:original, derivative_object_key=:derived,
                          content_hash=:hash, mime_type=:mime, width=:width, height=:height,
                          byte_size=:bytes, is_primary=true, updated_at=now() WHERE id=:id
                    """), {"id": media_id, "original": original_key, "derived": derivative_key,
                            "hash": digest, "mime": candidate.mime_type or detected_mime,
                            "width": width, "height": height, "bytes": len(original) + len(derivative)})
                _finish_item(engine, item["id"], "ready", len(candidates))
            else:
                state = "review_required" if candidates else "no_match"
                _finish_item(engine, item["id"], state, len(candidates))
        except Exception as exc:
            _finish_item(engine, item["id"], "failed", 0, exc)
    return _finalize(engine, run_id)


def _source(engine: Engine) -> dict:
    with engine.connect() as connection:
        row = connection.execute(text("SELECT * FROM source_registry WHERE source_key='wikimedia_commons'")).mappings().one()
    return dict(row)


def collect_media(engine: Engine, settings: Settings, statuses: list[str], limit: int | None,
                  dry_run: bool = False, ids: list[str] | None = None,
                  client: WikimediaClient | None = None, store: ObjectStore | None = None) -> dict:
    allowed = {"published", "ready", "review_required"}
    if not statuses or set(statuses) - allowed:
        raise ValueError(f"target statuses must be a subset of {sorted(allowed)}")
    targets = _targets(engine, statuses, limit, ids)
    if dry_run:
        return {"status": "dry_run", "target_count": len(targets), "targets": [
            {key: str(value) if key == "target_id" else value for key, value in target.items()}
            for target in targets
        ]}
    run_id = _create_run(engine, str(_source(engine)["id"]), statuses, limit, False, targets)
    return _process(engine, settings, run_id, client or WikimediaClient(settings), store or ObjectStore(settings))


def resume_media(engine: Engine, settings: Settings, run_id: str,
                 client: WikimediaClient | None = None, store: ObjectStore | None = None) -> dict:
    with engine.begin() as connection:
        connection.execute(text("UPDATE media_collection_runs SET status='running', finished_at=NULL WHERE id=:id"), {"id": run_id})
    return _process(engine, settings, run_id, client or WikimediaClient(settings), store or ObjectStore(settings), True)


def audit_media(engine: Engine, run_id: str) -> dict:
    with engine.connect() as connection:
        run = connection.execute(text("SELECT * FROM media_collection_runs WHERE id=:id"), {"id": run_id}).mappings().one()
        invalid = connection.execute(text("""
            SELECT count(*) FROM spot_media m JOIN media_collection_candidates c ON c.media_id=m.id
            JOIN media_collection_run_items i ON i.id=c.run_item_id
            WHERE i.run_id=:run AND m.status='ready' AND (
              m.license_status<>'verified' OR m.creator='' OR m.license_url='' OR
              m.attribution_text='' OR m.content_hash IS NULL OR m.original_object_key IS NULL OR
              m.derivative_object_key IS NULL)
        """), {"run": run_id}).scalar_one()
    return {"run_id": run_id, "status": run["status"], "metrics": run["metrics"], "invalid_ready_assets": invalid, "passed": invalid == 0}


def export_media(engine: Engine, run_id: str, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{run_id}-spot-media.jsonl"
    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT i.target_kind, i.target_id::text, i.target_name, i.status item_status,
              c.rank, m.source_page_id, m.source_page_url, m.original_url, m.title,
              m.creator, m.license_name, m.license_url, m.attribution_text, m.status,
              m.match_score::float, m.distance_meters, m.is_primary, m.content_hash,
              m.original_object_key, m.derivative_object_key, m.byte_size
            FROM media_collection_run_items i
            LEFT JOIN media_collection_candidates c ON c.run_item_id=i.id
            LEFT JOIN spot_media m ON m.id=c.media_id
            WHERE i.run_id=:run ORDER BY i.target_name, c.rank
        """), {"run": run_id}).mappings().all()
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(dict(row), ensure_ascii=False, default=str) + "\n")
    return path
