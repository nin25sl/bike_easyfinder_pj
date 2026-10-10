from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Interest(StrEnum):
    ANY = "any"
    SCENIC = "scenic"
    SEA = "sea"
    MOUNTAIN = "mountain"
    WINDING = "winding"
    CAFE = "cafe"
    FOOD = "food"
    ONSEN = "onsen"
    ROADSIDE_STATION = "roadside_station"
    NIGHT_VIEW = "night_view"
    HISTORIC = "historic"


class Coordinate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)


class SpotReaction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spot_id: UUID
    reaction: str = Field(pattern="^(interested|not_interested|visited)$")


class PreferenceProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spot_reactions: list[SpotReaction] = Field(default_factory=list, max_length=200)
    category_weights: dict[str, int] = Field(default_factory=dict)
    tag_weights: dict[str, int] = Field(default_factory=dict)

    @staticmethod
    def _check_weights(values: dict[str, int]) -> dict[str, int]:
        if any(value < -30 or value > 15 for value in values.values()):
            raise ValueError("weights must be between -30 and 15")
        return values

    def model_post_init(self, __context: object) -> None:
        self._check_weights(self.category_weights)
        self._check_weights(self.tag_weights)


class RecommendationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    origin: Coordinate
    available_minutes: int
    interests: list[Interest] = Field(min_length=1)
    allow_highway: bool
    locale: str = "ja-JP"
    preference_profile: PreferenceProfile = Field(default_factory=PreferenceProfile)

    def model_post_init(self, __context: object) -> None:
        if self.available_minutes not in {60, 120, 180, 240, 360, 600}:
            raise ValueError("unsupported available_minutes")


class RouteSummary(BaseModel):
    profile: str = "auto"
    encoded_polyline: str
    shape_format: str = "polyline6"


class Freshness(BaseModel):
    spot_verified_at: datetime
    route_generated_at: datetime
    hours_verified_at: datetime | None = None


class Constraints(BaseModel):
    opening_hours: str = "unknown"
    weather: str = "not_requested"
    road_information: str = "external_confirmation_required"


class WarningItem(BaseModel):
    code: str
    message: str


class RecommendationCandidate(BaseModel):
    spot_id: UUID
    name: str
    summary: str | None
    category: str
    tags: list[str]
    coordinate: Coordinate
    outbound_minutes: int
    stay_minutes: int
    return_minutes: int
    return_buffer_minutes: int = 15
    estimated_total_minutes: int
    return_eta: datetime | None
    distance_km: float
    score: float = Field(ge=0, le=100)
    reasons: list[str] = Field(min_length=1, max_length=3)
    route: RouteSummary
    freshness: Freshness
    constraints: Constraints = Field(default_factory=Constraints)


class RecommendationResponse(BaseModel):
    recommendation_id: UUID
    generated_at: datetime
    recommendation_rule_version: str
    data_version: str
    candidates: list[RecommendationCandidate] = Field(max_length=5)
    warnings: list[WarningItem]


class InteractionEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    event_id: UUID
    session_id: UUID
    recommendation_id: UUID
    spot_id: UUID
    event_type: str = Field(pattern="^(shown|interested|not_interested|visited|selected|route_started)$")
    occurred_at: datetime
    rank: int | None = Field(default=None, ge=1, le=5)
    available_minutes: int | None = None
    interests: list[Interest] = Field(default_factory=list)


class InteractionBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    events: list[InteractionEvent] = Field(min_length=1, max_length=50)


class AcceptedResponse(BaseModel):
    accepted: int

