from __future__ import annotations

import json
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import Connection

from collection_worker.config import Settings
from collection_worker.logging import emit


def create_db_engine(settings: Settings) -> Engine:
    return create_engine(settings.database_url, pool_pre_ping=True, future=True)


@contextmanager
def transaction(engine: Engine) -> Iterator[Connection]:
    with engine.begin() as connection:
        yield connection


def apply_migrations(engine: Engine) -> None:
    candidates = [
        Path(__file__).resolve().parents[2] / "migrations",
        Path.cwd() / "migrations",
        Path("/app/migrations"),
    ]
    migrations_dir = next((path for path in candidates if path.is_dir()), None)
    if migrations_dir is None:
        raise FileNotFoundError("Database migrations directory was not packaged")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE IF NOT EXISTS schema_migrations (version TEXT PRIMARY KEY, applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"))
    for migration in sorted(migrations_dir.glob("*.sql")):
        with engine.begin() as connection:
            applied = connection.execute(
                text("SELECT 1 FROM schema_migrations WHERE version=:version"),
                {"version": migration.name},
            ).scalar_one_or_none()
            if applied:
                continue
            raw = connection.connection.driver_connection
            with raw.cursor() as cursor:
                cursor.execute(migration.read_text(encoding="utf-8"))
            connection.execute(
                text("INSERT INTO schema_migrations(version) VALUES (:version) ON CONFLICT DO NOTHING"),
                {"version": migration.name},
            )
            emit("migration_applied", version=migration.name)


def sync_source_registry(engine: Engine, settings: Settings) -> None:
    sql = text(
        """
        INSERT INTO source_registry (
            id, source_key, source_type, base_url, domain, approval_status,
            license_status, license_name, terms_url, attribution_text,
            raw_storage_policy, refresh_interval_days, rate_limit_per_minute,
            request_timeout_seconds, max_pages_per_run, config, reviewed_at
        ) VALUES (
            :id, :source_key, :source_type, :base_url, :domain, :approval_status,
            :license_status, :license_name, :terms_url, :attribution_text,
            :raw_storage_policy, :refresh_interval_days, :rate_limit_per_minute,
            :request_timeout_seconds, :max_pages_per_run, CAST(:config AS jsonb),
            CASE WHEN :approval_status = 'approved' THEN now() ELSE NULL END
        )
        ON CONFLICT (source_key) DO UPDATE SET
            source_type=EXCLUDED.source_type,
            base_url=EXCLUDED.base_url,
            domain=EXCLUDED.domain,
            approval_status=EXCLUDED.approval_status,
            license_status=EXCLUDED.license_status,
            license_name=EXCLUDED.license_name,
            terms_url=EXCLUDED.terms_url,
            attribution_text=EXCLUDED.attribution_text,
            raw_storage_policy=EXCLUDED.raw_storage_policy,
            refresh_interval_days=EXCLUDED.refresh_interval_days,
            rate_limit_per_minute=EXCLUDED.rate_limit_per_minute,
            request_timeout_seconds=EXCLUDED.request_timeout_seconds,
            max_pages_per_run=EXCLUDED.max_pages_per_run,
            config=EXCLUDED.config,
            updated_at=now()
        """
    )
    with engine.begin() as connection:
        for key, source in settings.sources.items():
            domain = None
            if source.base_url:
                from urllib.parse import urlsplit

                domain = urlsplit(source.base_url).hostname
            connection.execute(
                sql,
                {
                    "id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"source:{key}")),
                    "source_key": key,
                    "source_type": source.source_type,
                    "base_url": source.base_url,
                    "domain": domain,
                    "approval_status": source.approval_status,
                    "license_status": source.license_status,
                    "license_name": source.license_name,
                    "terms_url": source.terms_url,
                    "attribution_text": source.attribution_text,
                    "raw_storage_policy": source.raw_storage_policy,
                    "refresh_interval_days": source.refresh_interval_days,
                    "rate_limit_per_minute": source.rate_limit_per_minute,
                    "request_timeout_seconds": source.request_timeout_seconds,
                    "max_pages_per_run": source.max_pages_per_run,
                    "config": json.dumps(source.config, ensure_ascii=False, default=str),
                },
            )
