from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class Evidence(BaseModel):
    model_config = ConfigDict(extra="forbid")
    field: str
    excerpt: str


class SpotObservation(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None
    name_reading: str | None
    address: str | None
    latitude: float | None = Field(ge=-90, le=90)
    longitude: float | None = Field(ge=-180, le=180)
    description_facts: list[str]
    source_categories: list[str]
    features: list[str]
    opening_hours_text: str | None
    business_status: Literal["open", "temporarily_closed", "permanently_closed", "unknown"]
    parking: Literal["available", "unavailable", "unknown"]
    motorcycle_access: Literal["allowed", "not_allowed", "unknown"]
    road_access: Literal["accessible", "restricted", "unknown"]
    suggested_stay_minutes: int | None = Field(ge=0)
    official_url: str | None
    touring_relevance: float | None = Field(default=None, ge=0, le=1)
    touring_reasons: list[str] = Field(default_factory=list)
    evidence: list[Evidence]


class SpotObservationBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spots: list[SpotObservation]


class DiscoveredRecord(BaseModel):
    source_record_id: str
    source_url: str
    payload: dict[str, Any] = Field(default_factory=dict)
    raw_text: str | None = None
    content_type: str = "application/json"
    response_headers: dict[str, str] = Field(default_factory=dict)
    http_status: int | None = None
    title: str | None = None


class DiscoveryPage(BaseModel):
    """A durable adapter boundary used by checkpoint-aware collection runs."""

    records: list[DiscoveredRecord] = Field(default_factory=list)
    checkpoint: dict[str, Any] = Field(default_factory=dict)
    complete: bool = False


class Region(BaseModel):
    id: str
    region_code: str
    region_kind: str
    name_ja: str
    prefecture_code: str
    parent_region_code: str | None
    dataset_version: str
    bbox: tuple[float, float, float, float]
    geometry_wkb: bytes | None = None


class ObservationInput(BaseModel):
    field_name: str
    value: Any
    raw_label: str | None = None
    extraction_method: Literal["source_native", "rule", "openai", "manual"]
    confidence: float = Field(ge=0, le=1)
    evidence_excerpt: str | None = None
    observed_at: datetime | None = None
    rule_version: str | None = None


class NormalizedCandidate(BaseModel):
    name: str | None = None
    address: str | None = None
    latitude: float | None = Field(default=None, ge=-90, le=90)
    longitude: float | None = Field(default=None, ge=-180, le=180)
    source_categories: list[str] = Field(default_factory=list)
    features: list[str] = Field(default_factory=list)
    attributes: dict[str, Any] = Field(default_factory=dict)
    observations: list[ObservationInput] = Field(default_factory=list)


class DiscoveryCitation(BaseModel):
    url: HttpUrl
    title: str
