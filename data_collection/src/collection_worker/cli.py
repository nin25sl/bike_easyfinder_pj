from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated

import typer

from collection_worker.config import load_settings
from collection_worker.db import (
    apply_migrations,
    create_db_engine,
    sync_source_registry,
)
from collection_worker.errors import ConfigurationError
from collection_worker.exporter import export_run
from collection_worker.logging import configure_logging
from collection_worker.media import audit_media, collect_media, export_media, resume_media
from collection_worker.pipeline import collect as run_collection
from collection_worker.pipeline import collect_all as run_collection_batch
from collection_worker.pipeline import resume as resume_collection
from collection_worker.pipeline import resume_batch as resume_collection_batch
from collection_worker.regions import sync_regions
from collection_worker.repository import Repository
from collection_worker.utils import validate_local_government_code

app = typer.Typer(help="Source-aware Spot data collection worker", no_args_is_help=True)
db_app = typer.Typer(help="Database operations")
regions_app = typer.Typer(help="Administrative-region operations")
runs_app = typer.Typer(help="Collection-run operations")
batches_app = typer.Typer(help="Collection-batch operations")
media_app = typer.Typer(help="Licensed Spot image collection operations")
app.add_typer(db_app, name="db")
app.add_typer(regions_app, name="regions")
app.add_typer(runs_app, name="runs")
app.add_typer(batches_app, name="batches")
app.add_typer(media_app, name="media")


def _print(payload: object) -> None:
    typer.echo(json.dumps(payload, ensure_ascii=False, indent=2, default=str))


def _fail(exc: Exception) -> None:
    typer.echo(f"ERROR [{getattr(exc, 'code', type(exc).__name__)}] {exc}", err=True)
    raise typer.Exit(code=getattr(exc, "exit_code", 5))


@db_app.command("migrate")
def migrate(config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    """Apply database migrations and synchronize the Source registry."""
    try:
        settings = load_settings(config)
        engine = create_db_engine(settings)
        apply_migrations(engine)
        sync_source_registry(engine, settings)
        _print({"status": "completed"})
    except Exception as exc:
        _fail(exc)


@regions_app.command("sync")
def regions_sync(
    dataset_version: Annotated[str, typer.Option("--dataset-version")] = "latest",
    input_path: Annotated[Path | None, typer.Option("--input")] = None,
    config: Annotated[Path | None, typer.Option("--config")] = None,
) -> None:
    """Load N03 administrative polygons from a local file or configured URL."""
    try:
        settings = load_settings(config)
        engine = create_db_engine(settings)
        sync_source_registry(engine, settings)
        count = sync_regions(engine, settings, dataset_version, input_path)
        _print({"status": "completed", "dataset_version": dataset_version, "region_count": count})
    except Exception as exc:
        _fail(exc)


@app.command("collect")
def collect(
    region_code: Annotated[str | None, typer.Option("--region-code")] = None,
    prefecture_code: Annotated[str | None, typer.Option("--prefecture-code")] = None,
    sources: Annotated[str, typer.Option("--sources")] = "osm_overpass,public_open_data,manual_seed",
    mode: Annotated[str, typer.Option("--mode")] = "initial",
    limit: Annotated[int | None, typer.Option("--limit", min=1)] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    config: Annotated[Path | None, typer.Option("--config")] = None,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    """Collect Spot candidates for a municipality, ward, designated city, or prefecture."""
    configure_logging(verbose)
    try:
        if bool(region_code) == bool(prefecture_code):
            raise ConfigurationError("Specify exactly one of --region-code or --prefecture-code")
        if mode not in {"initial", "refresh"}:
            raise ConfigurationError("--mode must be initial or refresh")
        code = validate_local_government_code(region_code or prefecture_code or "")
        if prefecture_code and len(code) != 2:
            raise ConfigurationError("--prefecture-code must contain two digits")
        selected = [item.strip() for item in sources.split(",") if item.strip()]
        settings = load_settings(config)
        result = run_collection(
            create_db_engine(settings), settings, code, selected, mode, limit=limit, dry_run=dry_run
        )
        _print(result)
        if result.get("status") in {"partial", "failed"}:
            raise typer.Exit(code=2)
    except typer.Exit:
        raise
    except Exception as exc:
        _fail(exc)


@runs_app.command("resume")
def runs_resume(
    run_id: str,
    failed_only: Annotated[bool, typer.Option("--failed-only")] = True,
    config: Annotated[Path | None, typer.Option("--config")] = None,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    """Resume a failed, partial, or cancelled run using its original identity."""
    configure_logging(verbose)
    try:
        settings = load_settings(config)
        _print(resume_collection(create_db_engine(settings), settings, run_id))
    except Exception as exc:
        _fail(exc)


@app.command("collect-all")
def collect_all_command(
    profile: Annotated[str, typer.Option("--profile")],
    region_group: Annotated[str, typer.Option("--region-group")],
    mode: Annotated[str, typer.Option("--mode")] = "initial",
    limit: Annotated[int | None, typer.Option("--limit", min=1)] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    config: Annotated[Path | None, typer.Option("--config")] = None,
    verbose: Annotated[bool, typer.Option("--verbose")] = False,
) -> None:
    """Run a configured source profile for every region in a region group."""
    configure_logging(verbose)
    try:
        if mode not in {"initial", "refresh"}:
            raise ConfigurationError("--mode must be initial or refresh")
        settings = load_settings(config)
        result = run_collection_batch(
            create_db_engine(settings), settings, profile, region_group, mode,
            limit=limit, dry_run=dry_run,
        )
        _print(result)
        if result.get("status") in {"partial", "failed"}:
            raise typer.Exit(code=2)
    except typer.Exit:
        raise
    except Exception as exc:
        _fail(exc)


@batches_app.command("resume")
def batches_resume(
    batch_id: str,
    failed_only: Annotated[bool, typer.Option("--failed-only")] = True,
    config: Annotated[Path | None, typer.Option("--config")] = None,
) -> None:
    try:
        settings = load_settings(config)
        result = resume_collection_batch(create_db_engine(settings), settings, batch_id)
        _print(result)
        if result.get("status") in {"partial", "failed"}:
            raise typer.Exit(code=2)
    except typer.Exit:
        raise
    except Exception as exc:
        _fail(exc)


@batches_app.command("show")
def batches_show(batch_id: str, config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    try:
        settings = load_settings(config)
        _print(Repository(create_db_engine(settings)).batch(batch_id))
    except Exception as exc:
        _fail(exc)


@runs_app.command("show")
def runs_show(run_id: str, config: Annotated[Path | None, typer.Option("--config")] = None) -> None:
    try:
        settings = load_settings(config)
        _print(Repository(create_db_engine(settings)).run(run_id))
    except Exception as exc:
        _fail(exc)


@app.command("export")
def export(
    run_id: Annotated[str, typer.Option("--run-id")],
    output_format: Annotated[str, typer.Option("--format")] = "jsonl",
    status: Annotated[str | None, typer.Option("--status")] = None,
    view: Annotated[str, typer.Option("--view")] = "candidate",
    config: Annotated[Path | None, typer.Option("--config")] = None,
) -> None:
    """Export Source-bearing SpotCandidate v1 data without raw bodies."""
    try:
        settings = load_settings(config)
        paths = export_run(create_db_engine(settings), run_id, settings.output_dir, output_format, status, view)
        _print({"status": "completed", "files": [str(path) for path in paths]})
    except Exception as exc:
        _fail(exc)


@media_app.command("collect")
def media_collect(
    target: Annotated[str, typer.Option("--target")] = "published,ready,review_required",
    source: Annotated[str, typer.Option("--source")] = "wikimedia_commons",
    limit: Annotated[int | None, typer.Option("--limit", min=1)] = None,
    spot_id: Annotated[list[str] | None, typer.Option("--spot-id")] = None,
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    config: Annotated[Path | None, typer.Option("--config")] = None,
) -> None:
    """Collect reusable Wikimedia Commons images for existing Spots."""
    try:
        if source != "wikimedia_commons":
            raise ConfigurationError("Only --source wikimedia_commons is supported")
        statuses = [value.strip() for value in target.split(",") if value.strip()]
        settings = load_settings(config)
        result = collect_media(
            create_db_engine(settings), settings, statuses, limit,
            dry_run=dry_run, ids=spot_id,
        )
        _print(result)
        if result.get("status") in {"partial", "failed"}:
            raise typer.Exit(code=2)
    except typer.Exit:
        raise
    except Exception as exc:
        _fail(exc)


@media_app.command("resume")
def media_resume(
    run_id: str,
    failed_only: Annotated[bool, typer.Option("--failed-only")] = True,
    config: Annotated[Path | None, typer.Option("--config")] = None,
) -> None:
    """Resume failed items in an image collection run."""
    try:
        if not failed_only:
            raise ConfigurationError("Only --failed-only resume is supported")
        settings = load_settings(config)
        result = resume_media(create_db_engine(settings), settings, run_id)
        _print(result)
        if result.get("status") in {"partial", "failed"}:
            raise typer.Exit(code=2)
    except typer.Exit:
        raise
    except Exception as exc:
        _fail(exc)


@media_app.command("audit")
def media_audit(
    run_id: Annotated[str, typer.Option("--run-id")],
    config: Annotated[Path | None, typer.Option("--config")] = None,
) -> None:
    """Check that ready images have complete license, attribution, and storage metadata."""
    try:
        settings = load_settings(config)
        result = audit_media(create_db_engine(settings), run_id)
        _print(result)
        if not result["passed"]:
            raise typer.Exit(code=2)
    except typer.Exit:
        raise
    except Exception as exc:
        _fail(exc)


@media_app.command("export")
def media_export(
    run_id: Annotated[str, typer.Option("--run-id")],
    config: Annotated[Path | None, typer.Option("--config")] = None,
) -> None:
    """Export an auditable JSONL manifest for an image collection run."""
    try:
        settings = load_settings(config)
        path = export_media(create_db_engine(settings), run_id, settings.output_dir)
        _print({"status": "completed", "file": str(path)})
    except Exception as exc:
        _fail(exc)
