from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, model_validator

from collection_worker.errors import ConfigurationError


class CollectionConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    checkpoint_every: int = Field(default=100, gt=0)
    raw_retention_days: int = Field(default=90, gt=0)
    outside_region_review_meters: int = Field(default=500, ge=0)
    duplicate_distance_meters: int = Field(default=100, gt=0)
    duplicate_name_similarity: float = Field(default=0.8, ge=0, le=1)
    max_response_bytes: int = Field(default=10_485_760, gt=0)
    max_item_attempts: int = Field(default=3, gt=0, le=20)
    entity_resolution_rule_version: str = "entity-resolution-v1"
    field_selection_rule_version: str = "field-selection-v1"
    touring_relevance_rule_version: str = "touring-relevance-v1"


class OpenAIConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    discovery_model: str = "gpt-6-astra"
    extraction_model: str = "gpt-6-luna"
    store: bool = False
    request_timeout_seconds: int = Field(default=120, gt=0)
    max_retries: int = Field(default=3, ge=0, le=10)
    run_budget_jpy: float = Field(default=500, gt=0)
    monthly_budget_jpy: float = Field(default=3000, gt=0)
    prompt_version: str = "spot-collection-v1"

    @model_validator(mode="after")
    def require_store_false(self) -> "OpenAIConfig":
        if self.store:
            raise ValueError("openai.store must remain false")
        return self


class SourceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal[
        "n03",
        "osm_overpass",
        "osm_pbf",
        "public_open_data",
        "official_web",
        "general_web",
        "touring_media",
        "openai_web_discovery",
        "manual_seed",
    ]
    approval_status: Literal["pending_review", "approved", "suspended", "retired", "rejected"]
    license_status: Literal["verified", "restricted", "unknown", "prohibited"]
    license_name: str | None = None
    terms_url: str | None = None
    attribution_text: str | None = None
    raw_storage_policy: Literal["full_allowed", "facts_only", "metadata_only", "prohibited"]
    base_url: str | None = None
    rate_limit_per_minute: int = Field(gt=0)
    request_timeout_seconds: int = Field(gt=0)
    max_pages_per_run: int = Field(gt=0)
    refresh_interval_days: int | None = Field(default=None, gt=0)
    region_codes: list[str] = Field(default_factory=list)
    config: dict[str, Any] = Field(default_factory=dict)


class CollectionProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sources: list[str]
    run_resolution: bool = True
    run_field_selection: bool = True


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

    collection: CollectionConfig
    openai: OpenAIConfig
    sources: dict[str, SourceConfig]
    region_groups: dict[str, list[str]] = Field(default_factory=dict)
    profiles: dict[str, CollectionProfile] = Field(default_factory=dict)
    database_url: str
    output_dir: Path
    cache_dir: Path
    config_path: Path

    @property
    def openai_api_key(self) -> str | None:
        return os.getenv("OPENAI_API_KEY") or None


def load_settings(path: str | Path | None = None) -> Settings:
    config_path = Path(path or os.getenv("COLLECTION_CONFIG", "data_collection/config/sources.yaml"))
    if not config_path.exists():
        raise ConfigurationError(f"Configuration file not found: {config_path}")
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
        raw["database_url"] = os.getenv(
            "DATABASE_URL",
            "postgresql+psycopg://bike:bike_local_only@localhost:5432/bike_easyfinder",
        )
        raw["output_dir"] = Path(os.getenv("OUTPUT_DIR", "data_collection/output"))
        raw["cache_dir"] = Path(os.getenv("CACHE_DIR", "data_collection/cache"))
        raw["config_path"] = config_path
        settings = Settings.model_validate(raw)
    except Exception as exc:
        raise ConfigurationError(f"Invalid configuration: {exc}") from exc
    if not settings.sources:
        raise ConfigurationError("At least one source must be configured")
    return settings
