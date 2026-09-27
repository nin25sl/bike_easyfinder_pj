from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any

from sqlalchemy import Engine

from collection_worker.adapters import (
    ManualSeedAdapter,
    OpenAIDiscoveryAdapter,
    OpenDataAdapter,
    OSMOverpassAdapter,
    OSMPBFAdapter,
)
from collection_worker.config import Settings
from collection_worker.contracts import DiscoveredRecord, NormalizedCandidate, Region
from collection_worker.db import sync_source_registry
from collection_worker.errors import ConfigurationError, PolicyError
from collection_worker.logging import emit
from collection_worker.normalize import normalize_payload, normalized_from_ai
from collection_worker.openai_client import OpenAIExtractor
from collection_worker.quality import assess_candidate, flag_duplicates
from collection_worker.regions import resolve_region
from collection_worker.repository import Repository
from collection_worker.utils import canonicalize_url, redact_url_queries


ADAPTERS = {
    "manual_seed": ManualSeedAdapter,
    "public_open_data": OpenDataAdapter,
    "openai_web_discovery": OpenAIDiscoveryAdapter,
    "osm_overpass": OSMOverpassAdapter,
    "osm_pbf": OSMPBFAdapter,
}


def settings_snapshot(settings: Settings, sources: list[str]) -> dict[str, Any]:
    raw = settings.config_path.read_bytes()
    return {
        "config_sha256": hashlib.sha256(raw).hexdigest(),
        "sources": sources,
        "openai_prompt_version": settings.openai.prompt_version,
        "openai_discovery_model": settings.openai.discovery_model,
        "openai_extraction_model": settings.openai.extraction_model,
    }


def validate_sources(settings: Settings, sources: list[str]) -> None:
    unknown = [key for key in sources if key not in settings.sources]
    if unknown:
        raise ConfigurationError(f"Unknown sources: {', '.join(unknown)}")
    unsupported = [key for key in sources if settings.sources[key].source_type not in ADAPTERS]
    if unsupported:
        raise ConfigurationError(f"Sources have no collection adapter: {', '.join(unsupported)}")
    blocked = [key for key in sources if settings.sources[key].approval_status != "approved"]
    if blocked:
        raise PolicyError(f"Sources are not approved: {', '.join(blocked)}")
    if "openai_web_discovery" in sources and not settings.openai_api_key:
        raise PolicyError("OPENAI_API_KEY is required for openai_web_discovery")


def dry_run_summary(region: Region, settings: Settings, sources: list[str], limit: int | None) -> dict:
    return {
        "region_code": region.region_code,
        "region_name": region.name_ja,
        "region_kind": region.region_kind,
        "dataset_version": region.dataset_version,
        "sources": [
            {
                "source_key": key,
                "source_type": settings.sources[key].source_type,
                "license_status": settings.sources[key].license_status,
                "storage_policy": settings.sources[key].raw_storage_policy,
            }
            for key in sources
        ],
        "limit": limit,
        "openai_budget": {
            "run_budget_jpy": settings.openai.run_budget_jpy,
            "monthly_budget_jpy": settings.openai.monthly_budget_jpy,
            "store": settings.openai.store,
        },
    }


def collect(
    engine: Engine,
    settings: Settings,
    region_code: str,
    sources: list[str],
    mode: str,
    limit: int | None = None,
    dry_run: bool = False,
    existing_run_id: str | None = None,
) -> dict:
    validate_sources(settings, sources)
    region = resolve_region(engine, region_code)
    if dry_run:
        return dry_run_summary(region, settings, sources, limit)
    sync_source_registry(engine, settings)

    repository = Repository(engine)
    snapshot = settings_snapshot(settings, sources)
    if existing_run_id:
        run = repository.run(existing_run_id)
        prior = run["config_snapshot"]
        if prior.get("config_sha256") != snapshot["config_sha256"]:
            raise ConfigurationError("Configuration changed since this run; start a new run instead")
        repository.reopen_run(existing_run_id)
        run_id = existing_run_id
    else:
        run_id = repository.create_run(region, mode, sources, snapshot)

    metrics = {"discovered": 0, "ready": 0, "review_required": 0, "rejected": 0, "duplicates": 0}
    errors: dict[str, dict[str, str]] = {}
    touched: set[str] = set()
    emit("collection_started", run_id=run_id, region_code=region.region_code, sources=sources)

    for source_key in sources:
        source = settings.sources[source_key]
        source_row = repository.source(source_key)
        adapter_class = ADAPTERS[source.source_type]
        adapter = adapter_class(source_key, source, settings)
        try:
            records: Iterable[DiscoveredRecord] = adapter.discover(region, limit=limit)
            for record in records:
                record = record.model_copy(update={"source_url": canonicalize_url(record.source_url)})
                metrics["discovered"] += 1
                if source.source_type == "openai_web_discovery":
                    repository.register_pending_domain(record.source_url)
                item_id = repository.upsert_item(
                    run_id, str(source_row["id"]), region.id, source.source_type, record
                )
                raw_id = repository.save_raw(
                    item_id, record, source, settings.collection.raw_retention_days
                )
                candidates = _normalize_record(settings, source.config, record)
                for index, (candidate_record, candidate, ai_result) in enumerate(candidates):
                    candidate_id = repository.upsert_candidate(region, source_key, candidate_record, candidate)
                    touched.add(candidate_id)
                    for observation in candidate.observations:
                        repository.add_observation(
                            candidate_id, item_id, candidate_record, source, observation
                        )
                    if ai_result is not None:
                        repository.record_ai_run(
                            run_id,
                            raw_id,
                            "observation_extraction",
                            ai_result,
                            settings.openai.prompt_version,
                        )
                    status = assess_candidate(engine, repository, candidate_id, settings)
                    metrics[status] += 1
                    repository.update_item(item_id, status)
                if not candidates:
                    repository.update_item(item_id, "review_required", "NO_NORMALIZED_CANDIDATE")
                    metrics["review_required"] += 1
            metadata = getattr(adapter, "last_metadata", None)
            if metadata:
                repository.record_ai_run(
                    run_id,
                    None,
                    "source_discovery",
                    metadata,
                    settings.openai.prompt_version,
                )
        except Exception as exc:
            code = getattr(exc, "code", type(exc).__name__)
            errors[source_key] = {"code": str(code), "message": redact_url_queries(str(exc))[:1000]}
            emit(
                "source_failed",
                severity="ERROR",
                run_id=run_id,
                region_code=region.region_code,
                source_id=source_key,
                error_code=code,
            )

    metrics["duplicates"] = flag_duplicates(engine, repository, region.id, settings)
    status = "partial" if errors and metrics["discovered"] else ("failed" if errors else "completed")
    repository.finish_run(run_id, status, metrics, errors)
    emit("collection_finished", run_id=run_id, region_code=region.region_code, status=status, **metrics)
    return {"run_id": run_id, "status": status, "metrics": metrics, "errors": errors}


def _normalize_record(
    settings: Settings,
    source_config: dict[str, Any],
    record: DiscoveredRecord,
) -> list[tuple[DiscoveredRecord, NormalizedCandidate, Any | None]]:
    use_ai = bool(source_config.get("ai_extract") or record.payload.get("_ai_extract"))
    if not use_ai:
        method = "openai" if record.content_type == "application/x.openai-citation" else "source_native"
        return [(record, normalize_payload(record.payload, method=method), None)]
    if not record.raw_text:
        return []
    result = OpenAIExtractor(settings).extract(record.raw_text, record.source_url)
    if not result.batch:
        return []
    normalized = []
    for index, spot in enumerate(result.batch.spots):
        child = record.model_copy(update={"source_record_id": f"{record.source_record_id}#ai-{index}"})
        normalized.append((child, normalized_from_ai(spot), result))
    return normalized


def resume(engine: Engine, settings: Settings, run_id: str) -> dict:
    repository = Repository(engine)
    run = repository.run(run_id)
    if run["status"] not in {"failed", "partial", "cancelled"}:
        raise ConfigurationError(f"Run {run_id} is not resumable from status {run['status']}")
    region = repository.region_for_run(run_id)
    return collect(
        engine,
        settings,
        region.region_code,
        list(run["requested_sources"]),
        run["mode"],
        existing_run_id=run_id,
    )
