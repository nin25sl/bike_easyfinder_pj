from __future__ import annotations

import hashlib
from typing import Any

from sqlalchemy import Engine, text

from collection_worker.adapters import (
    GeneralWebAdapter,
    ManualSeedAdapter,
    OfficialWebAdapter,
    OpenAIDiscoveryAdapter,
    OpenDataAdapter,
    OSMOverpassAdapter,
    OSMPBFAdapter,
    TouringMediaAdapter,
)
from collection_worker.config import Settings
from collection_worker.contracts import (
    DiscoveredRecord,
    NormalizedCandidate,
    ObservationInput,
    Region,
)
from collection_worker.db import sync_source_registry
from collection_worker.errors import (
    ConfigurationError,
    PolicyError,
    TemporarySourceError,
)
from collection_worker.logging import emit
from collection_worker.normalize import normalize_payload, normalized_from_ai
from collection_worker.openai_client import OpenAIExtractor
from collection_worker.quality import assess_candidate, flag_duplicates
from collection_worker.regions import resolve_region
from collection_worker.repository import Repository
from collection_worker.resolution import resolve_entities, select_entity_fields
from collection_worker.utils import canonicalize_url, redact_url_queries, stable_hash

ADAPTERS = {
    "manual_seed": ManualSeedAdapter,
    "public_open_data": OpenDataAdapter,
    "openai_web_discovery": OpenAIDiscoveryAdapter,
    "osm_overpass": OSMOverpassAdapter,
    "osm_pbf": OSMPBFAdapter,
    "official_web": OfficialWebAdapter,
    "general_web": GeneralWebAdapter,
    "touring_media": TouringMediaAdapter,
}


def settings_snapshot(settings: Settings, sources: list[str]) -> dict[str, Any]:
    raw = settings.config_path.read_bytes()
    return {
        "config_sha256": hashlib.sha256(raw).hexdigest(),
        "sources": sources,
        "openai_prompt_version": settings.openai.prompt_version,
        "openai_discovery_model": settings.openai.discovery_model,
        "openai_extraction_model": settings.openai.extraction_model,
        "schema_version": "002_resolution_batches",
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
    prohibited = [
        key for key in sources
        if settings.sources[key].license_status == "prohibited"
        or settings.sources[key].raw_storage_policy == "prohibited"
    ]
    if prohibited:
        raise PolicyError(f"Sources are prohibited by policy: {', '.join(prohibited)}")
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
    batch_id: str | None = None,
    run_resolution: bool = True,
    run_field_selection: bool = True,
) -> dict:
    validate_sources(settings, sources)
    region = resolve_region(engine, region_code)
    if dry_run:
        return dry_run_summary(region, settings, sources, limit)
    sync_source_registry(engine, settings)

    repository = Repository(engine)
    snapshot = settings_snapshot(settings, sources)
    snapshot["region_dataset_version"] = region.dataset_version
    if existing_run_id:
        run = repository.run(existing_run_id)
        prior = run["config_snapshot"]
        compatibility_keys = ("config_sha256", "schema_version", "region_dataset_version")
        changed = [key for key in compatibility_keys if prior.get(key) != snapshot.get(key)]
        if changed or run["region_dataset_version"] != region.dataset_version:
            details = ", ".join(changed or ["region_dataset_version"])
            raise ConfigurationError(
                f"Run cannot be resumed because {details} changed; start a new run instead"
            )
        repository.reopen_run(existing_run_id)
        run_id = existing_run_id
    else:
        run_id = repository.create_run(region, mode, sources, snapshot, batch_id=batch_id)

    metrics = {
        "discovered": 0, "ready": 0, "review_required": 0, "rejected": 0,
        "duplicates": 0, "retried": 0, "unchanged": 0,
        "not_seen": 0,
    }
    errors: dict[str, dict[str, str]] = {}
    touched: set[str] = set()
    emit("collection_started", run_id=run_id, region_code=region.region_code, sources=sources)

    checkpoints = repository.checkpoint(run_id)
    for source_key in sources:
        source = settings.sources[source_key]
        if source.region_codes and region.region_code not in source.region_codes and region.prefecture_code not in source.region_codes:
            continue
        source_checkpoint = dict(checkpoints.get(source_key) or {})
        if existing_run_id and source_checkpoint.get("complete"):
            continue
        source_row = repository.source(source_key)
        adapter_class = ADAPTERS[source.source_type]
        adapter = adapter_class(source_key, source, settings)
        try:
            pages = adapter.iter_pages(region, limit=limit, checkpoint=source_checkpoint)
            for page in pages:
                page_start = dict(source_checkpoint)
                page_failed = False
                for record in page.records:
                    item_id: str | None = None
                    try:
                        record = record.model_copy(update={"source_url": canonicalize_url(record.source_url)})
                        metrics["discovered"] += 1
                        if source.source_type == "openai_web_discovery":
                            repository.register_pending_domain(record.source_url)
                        item_id = repository.upsert_item(
                            run_id, str(source_row["id"]), region.id, source.source_type, record
                        )
                        if existing_run_id:
                            item_state = repository.item_state(item_id)
                            if item_state["status"] in {"ready", "review_required", "rejected"}:
                                continue
                            if not item_state["retry_due"]:
                                page_failed = True
                                continue
                        raw_text = record.raw_text or __import__("json").dumps(
                            record.payload, ensure_ascii=False, sort_keys=True
                        )
                        unchanged = mode == "refresh" and repository.content_unchanged(
                            str(source_row["id"]), record.source_record_id, stable_hash(raw_text), run_id
                        )
                        raw_id = repository.save_raw(
                            item_id, record, source, settings.collection.raw_retention_days
                        )
                        if unchanged:
                            repository.update_item(item_id, "ready")
                            metrics["unchanged"] += 1
                            continue
                        candidates = _normalize_record(settings, source.config, record)
                        for candidate_record, candidate, ai_result in candidates:
                            candidate_id = repository.upsert_candidate(region, source_key, candidate_record, candidate)
                            touched.add(candidate_id)
                            for observation in candidate.observations:
                                repository.add_observation(
                                    candidate_id, item_id, candidate_record, source, observation
                                )
                            if ai_result is not None:
                                repository.record_ai_run(
                                    run_id, raw_id, "observation_extraction", ai_result,
                                    settings.openai.prompt_version,
                                )
                            status = assess_candidate(engine, repository, candidate_id, settings)
                            metrics[status] += 1
                            repository.update_item(item_id, status)
                        if not candidates:
                            repository.update_item(item_id, "review_required", "NO_NORMALIZED_CANDIDATE")
                            metrics["review_required"] += 1
                    except TemporarySourceError as exc:
                        if item_id:
                            attempts = repository.mark_item_retry(
                                item_id, exc.code, redact_url_queries(str(exc)),
                            )
                            if attempts >= settings.collection.max_item_attempts:
                                repository.update_item(item_id, "review_required", exc.code, str(exc)[:1000])
                                metrics["review_required"] += 1
                                errors[f"{source_key}:{record.source_record_id}"] = {
                                    "code": "RETRY_EXHAUSTED", "message": str(exc)[:1000]
                                }
                                continue
                        metrics["retried"] += 1
                        page_failed = True
                        errors[f"{source_key}:{record.source_record_id}"] = {"code": exc.code, "message": str(exc)[:1000]}
                    except Exception as exc:
                        if item_id:
                            repository.update_item(
                                item_id, "review_required", getattr(exc, "code", type(exc).__name__),
                                redact_url_queries(str(exc))[:1000],
                            )
                        metrics["review_required"] += 1
                        errors[f"{source_key}:{record.source_record_id}"] = {
                            "code": str(getattr(exc, "code", type(exc).__name__)), "message": str(exc)[:1000]
                        }
                if page_failed:
                    repository.save_checkpoint(run_id, source_key, {**page_start, "complete": False})
                    break
                source_checkpoint = dict(page.checkpoint)
                repository.save_checkpoint(run_id, source_key, {**page.checkpoint, "complete": page.complete})
            if mode == "refresh" and source_checkpoint.get("offset") is not None:
                latest_checkpoint = repository.checkpoint(run_id).get(source_key, {})
                if latest_checkpoint.get("complete"):
                    metrics["not_seen"] += repository.mark_source_not_seen(
                        run_id, region.id, str(source_row["id"])
                    )
            if source.source_type in {"official_web", "general_web", "touring_media"}:
                repository.mark_robots_checked(str(source_row["id"]))
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

    if run_resolution:
        metrics["resolution"] = resolve_entities(engine, repository, region.id, settings)
    metrics["duplicates"] = flag_duplicates(engine, repository, region.id, settings)
    if run_field_selection:
        metrics["field_selection"] = select_entity_fields(engine, repository, region.id, settings)
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
        candidate = normalized_from_ai(spot)
        if record.payload.get("_touring_signal"):
            signals = {item.lower() for item in [*spot.features, *spot.source_categories]}
            reasons = ["motorcycle_media_mentions"]
            for key in ("scenic", "winding", "cafe", "sunset", "mountain", "sea", "historic", "onsen"):
                if any(key in value for value in signals):
                    reasons.append(key)
            score = min(0.9, 0.55 + 0.05 * (len(reasons) - 1))
            candidate.observations.extend([
                ObservationInput(
                    field_name="touring_relevance", value=score, extraction_method="rule",
                    confidence=0.7, evidence_excerpt="Derived from an approved motorcycle-media mention",
                    rule_version=settings.collection.touring_relevance_rule_version,
                ),
                ObservationInput(
                    field_name="touring_reasons", value=reasons, extraction_method="rule",
                    confidence=0.7,
                    rule_version=settings.collection.touring_relevance_rule_version,
                ),
            ])
        normalized.append((child, candidate, result))
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


def collect_all(
    engine: Engine,
    settings: Settings,
    profile_name: str,
    region_group: str,
    mode: str,
    limit: int | None = None,
    dry_run: bool = False,
) -> dict:
    if profile_name not in settings.profiles:
        raise ConfigurationError(f"Unknown profile: {profile_name}")
    if region_group not in settings.region_groups:
        raise ConfigurationError(f"Unknown region group: {region_group}")
    profile = settings.profiles[profile_name]
    validate_sources(settings, profile.sources)
    regions = settings.region_groups[region_group]
    if dry_run:
        return {
            "status": "dry_run", "profile": profile_name, "region_group": region_group,
            "regions": regions, "sources": profile.sources, "mode": mode,
        }
    sync_source_registry(engine, settings)
    repository = Repository(engine)
    batch_id = repository.create_batch(profile_name, region_group, mode, regions, profile.sources)
    results: list[dict] = []
    errors: dict[str, dict] = {}
    for region_code in regions:
        applicable = [
            key for key in profile.sources
            if not settings.sources[key].region_codes
            or region_code in settings.sources[key].region_codes
            or region_code[:2] in settings.sources[key].region_codes
        ]
        for index, source_key in enumerate(applicable):
            error_key = f"{region_code}:{source_key}"
            finalize_region = index == len(applicable) - 1
            try:
                result = collect(
                    engine, settings, region_code, [source_key], mode, limit=limit,
                    batch_id=batch_id,
                    run_resolution=profile.run_resolution and finalize_region,
                    run_field_selection=profile.run_field_selection and finalize_region,
                )
                results.append({"region_code": region_code, "source_key": source_key, **result})
                if result["status"] != "completed":
                    errors[error_key] = result.get("errors", {})
            except Exception as exc:
                errors[error_key] = {
                    "code": getattr(exc, "code", type(exc).__name__),
                    "message": str(exc)[:1000],
                }
    status = "partial" if results and errors else ("failed" if errors else "completed")
    successful_regions = {
        region_code for region_code in regions
        if not any(key.startswith(f"{region_code}:") for key in errors)
        and any(item["region_code"] == region_code for item in results)
    }
    metrics = {
        "regions_total": len(regions), "regions_completed": len(successful_regions),
        "runs": len(results), "discovered": sum(item["metrics"].get("discovered", 0) for item in results),
    }
    repository.finish_batch(batch_id, status, metrics, errors)
    return {"batch_id": batch_id, "status": status, "metrics": metrics, "results": results, "errors": errors}


def resume_batch(engine: Engine, settings: Settings, batch_id: str) -> dict:
    repository = Repository(engine)
    batch = repository.batch(batch_id)
    with engine.connect() as connection:
        run_rows = connection.execute(text(
            """
            SELECT cr.id::text, cr.status, r.region_code, cr.requested_sources
            FROM collection_runs cr JOIN administrative_regions r ON r.id=cr.region_id
            WHERE cr.batch_id=:id ORDER BY cr.created_at
            """
        ), {"id": batch_id}).mappings().all()
    resumable = [row for row in run_rows if row["status"] in {"partial", "failed", "cancelled"}]
    results = []
    errors = {}
    for row in resumable:
        try:
            results.append({
                "region_code": row["region_code"],
                "source_key": row["requested_sources"][0],
                **resume(engine, settings, row["id"]),
            })
        except Exception as exc:
            errors[row["id"]] = {
                "code": getattr(exc, "code", type(exc).__name__), "message": str(exc)[:1000]
            }
    profile = settings.profiles.get(batch["profile_name"])
    if profile:
        existing_pairs = {
            (row["region_code"], source_key)
            for row in run_rows
            for source_key in row["requested_sources"]
        }
        for region_code in batch["requested_regions"]:
            applicable = [
                key for key in profile.sources
                if not settings.sources[key].region_codes
                or region_code in settings.sources[key].region_codes
                or region_code[:2] in settings.sources[key].region_codes
            ]
            for source_key in applicable:
                if (region_code, source_key) in existing_pairs:
                    continue
                try:
                    results.append({
                        "region_code": region_code,
                        "source_key": source_key,
                        **collect(
                            engine, settings, region_code, [source_key], batch["mode"],
                            batch_id=batch_id,
                            run_resolution=profile.run_resolution,
                            run_field_selection=profile.run_field_selection,
                        ),
                    })
                except Exception as exc:
                    errors[f"{region_code}:{source_key}"] = {
                        "code": getattr(exc, "code", type(exc).__name__), "message": str(exc)[:1000]
                    }
    with engine.connect() as connection:
        status_counts = dict(connection.execute(text(
            "SELECT status, count(*) FROM collection_runs WHERE batch_id=:id GROUP BY status"
        ), {"id": batch_id}).all())
    incomplete = sum(status_counts.get(key, 0) for key in ("partial", "failed", "cancelled", "running"))
    status = "partial" if errors or incomplete else "completed"
    metrics = {
        "resumed_runs": len(resumable),
        "completed": status_counts.get("completed", 0),
        "incomplete": incomplete,
    }
    repository.finish_batch(batch_id, status, metrics, errors)
    return {"batch_id": batch_id, "status": status, "metrics": metrics, "results": results, "errors": errors}
