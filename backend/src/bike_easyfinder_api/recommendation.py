from __future__ import annotations

import logging
import math
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from .contracts import (
    Constraints,
    Coordinate,
    Freshness,
    RecommendationCandidate,
    RecommendationRequest,
    RecommendationResponse,
    RouteSummary,
    WarningItem,
)
from .providers import RouteEstimate, RouteProvider, haversine_km

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Spot:
    id: UUID
    name: str
    summary: str | None
    category: str
    tags: tuple[str, ...]
    coordinate: Coordinate
    stay_minutes: int
    confidence: float
    popularity_score: float
    verified_at: datetime
    hours_verified_at: datetime | None = None


REACTION_WEIGHTS = {"interested": 15, "not_interested": -30, "visited": -12}
TIME_WINDOW_TOLERANCES = (15, 30, 45, 60)
MAX_ROUTE_CANDIDATES = 10


def search_radius_km(available_minutes: int) -> float:
    return min(250.0, available_minutes * 1.5)


def _interest_score(spot: Spot, request: RecommendationRequest) -> float:
    requested = {item.value for item in request.interests}
    if "any" in requested:
        return 20.0
    matched = requested.intersection(set(spot.tags) | {spot.category})
    return min(40.0, 20.0 * len(matched))


def _preference_score(spot: Spot, request: RecommendationRequest) -> float:
    profile = request.preference_profile
    total = profile.category_weights.get(spot.category, 0)
    total += sum(profile.tag_weights.get(tag, 0) for tag in spot.tags)
    for reaction in profile.spot_reactions:
        if reaction.spot_id == spot.id:
            total += REACTION_WEIGHTS[reaction.reaction]
    return float(max(-30, min(15, total)))


def _reasons(spot: Spot, request: RecommendationRequest, total: int) -> list[str]:
    requested = {item.value for item in request.interests}
    matching = sorted(requested.intersection(set(spot.tags)))
    reasons = [f"往復と滞在を含め約{total}分です"]
    if matching:
        reasons.insert(0, f"希望の「{matching[0]}」に合います")
    if spot.confidence >= 0.8:
        reasons.append("確認済み情報の信頼度が高い候補です")
    return reasons[:3]


def _diversify(
    candidates: list[RecommendationCandidate], target_minutes: int
) -> list[RecommendationCandidate]:
    remaining = list(candidates)
    result: list[RecommendationCandidate] = []
    while remaining and len(result) < 5:
        chosen_index = 0
        if result and remaining[0].category == result[-1].category:
            best_score = remaining[0].score
            alternative = next(
                (
                    index
                    for index, item in enumerate(remaining[1:], start=1)
                    if item.category != result[-1].category
                    and abs(item.estimated_total_minutes - target_minutes)
                    == abs(remaining[0].estimated_total_minutes - target_minutes)
                    and best_score - item.score <= 5
                ),
                None,
            )
            if alternative is not None:
                chosen_index = alternative
        result.append(remaining.pop(chosen_index))
    return result


def _approximate_total_minutes(
    origin: Coordinate, spot: Spot, allow_highway: bool
) -> int:
    road_km = haversine_km(origin, spot.coordinate) * 1.22
    average_kph = 55 if allow_highway else 42
    one_way = max(1, math.ceil(road_km / average_kph * 60))
    return one_way * 2 + spot.stay_minutes + 15


class RecommendationEngine:
    def __init__(
        self,
        route_provider: RouteProvider,
        rule_version: str,
        data_version: str,
        deadline_seconds: float = 4.0,
    ) -> None:
        self._route_provider = route_provider
        self._rule_version = rule_version
        self._data_version = data_version
        self._deadline_seconds = deadline_seconds

    def recommend(self, request: RecommendationRequest, spots: list[Spot]) -> RecommendationResponse:
        generated_at = datetime.now(UTC)
        warnings: list[WarningItem] = []
        ranked: list[RecommendationCandidate] = []
        eligible: list[Spot] = []
        for spot in spots:
            requested = {item.value for item in request.interests}
            if "any" not in requested and not requested.intersection(set(spot.tags) | {spot.category}):
                continue
            eligible.append(spot)
        eligible.sort(
            key=lambda spot: (
                abs(
                    _approximate_total_minutes(request.origin, spot, request.allow_highway)
                    - request.available_minutes
                ),
                str(spot.id),
            )
        )
        eligible = eligible[:MAX_ROUTE_CANDIDATES]

        estimates, route_failures = self._estimate_routes(request, eligible)
        evaluated: list[tuple[Spot, RouteEstimate, int]] = []
        for spot in eligible:
            route = estimates.get(spot.id)
            if route is None:
                continue

            total = route.outbound_minutes + spot.stay_minutes + route.return_minutes + 15
            evaluated.append((spot, route, total))

        applied_tolerance: int | None = None
        selected: list[tuple[Spot, RouteEstimate, int]] = []
        for tolerance in TIME_WINDOW_TOLERANCES:
            selected = [
                item for item in evaluated if abs(item[2] - request.available_minutes) <= tolerance
            ]
            if selected:
                applied_tolerance = tolerance
                break

        for spot, route, total in selected:
            difference = abs(request.available_minutes - total)
            time_fit = max(0.0, 25.0 * (1 - difference / max(applied_tolerance or 15, 1)))
            score = _interest_score(spot, request)
            score += time_fit
            score += _preference_score(spot, request)
            score += spot.confidence * 10
            score += spot.popularity_score
            score = round(max(0, min(100, score)), 1)
            return_eta = generated_at + timedelta(minutes=route.outbound_minutes + spot.stay_minutes)
            ranked.append(
                RecommendationCandidate(
                    spot_id=spot.id,
                    name=spot.name,
                    summary=spot.summary,
                    category=spot.category,
                    tags=list(spot.tags),
                    coordinate=spot.coordinate,
                    outbound_minutes=route.outbound_minutes,
                    stay_minutes=spot.stay_minutes,
                    return_minutes=route.return_minutes,
                    estimated_total_minutes=total,
                    return_eta=return_eta,
                    distance_km=route.distance_km,
                    score=score,
                    reasons=_reasons(spot, request, total),
                    route=RouteSummary(encoded_polyline=route.encoded_polyline),
                    freshness=Freshness(
                        spot_verified_at=spot.verified_at,
                        route_generated_at=route.generated_at,
                        hours_verified_at=spot.hours_verified_at,
                    ),
                    constraints=Constraints(),
                )
            )

        if route_failures and ranked:
            warnings.append(
                WarningItem(code="PARTIAL_ROUTE_FAILURE", message="一部候補の経路を取得できませんでした。")
            )
        if eligible and route_failures == len(eligible):
            raise RouteProviderUnavailable("all route estimates failed")
        if applied_tolerance is not None and applied_tolerance > TIME_WINDOW_TOLERANCES[0]:
            warnings.append(
                WarningItem(
                    code="TIME_WINDOW_EXPANDED",
                    message=(
                        "指定時間±15分の候補がなかったため、"
                        f"±{applied_tolerance}分まで範囲を広げました。"
                    ),
                )
            )

        ranked.sort(
            key=lambda item: (
                abs(item.estimated_total_minutes - request.available_minutes),
                -item.score,
                str(item.spot_id),
            )
        )
        return RecommendationResponse(
            recommendation_id=uuid4(),
            generated_at=generated_at,
            recommendation_rule_version=self._rule_version,
            data_version=self._data_version,
            candidates=_diversify(ranked, request.available_minutes),
            warnings=warnings,
        )

    def _estimate_routes(
        self, request: RecommendationRequest, spots: list[Spot]
    ) -> tuple[dict[UUID, RouteEstimate], int]:
        if not spots:
            return {}, 0
        executor = ThreadPoolExecutor(max_workers=min(5, len(spots)))
        futures = {
            executor.submit(
                self._route_provider.estimate,
                request.origin,
                spot.coordinate,
                allow_highway=request.allow_highway,
                spot_id=spot.id,
                stay_minutes=spot.stay_minutes,
            ): spot.id
            for spot in spots
        }
        estimates: dict[UUID, RouteEstimate] = {}
        try:
            for future in as_completed(futures, timeout=max(0.1, self._deadline_seconds - 0.1)):
                try:
                    estimates[futures[future]] = future.result()
                except Exception as error:  # noqa: BLE001 - provider failures are isolated per spot
                    logger.warning(
                        "route estimate failed",
                        extra={
                            "spot_id": str(futures[future]),
                            "error_type": type(error).__name__,
                        },
                    )
        except TimeoutError:
            pass
        finally:
            for future in futures:
                future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
        return estimates, len(spots) - len(estimates)


class RouteProviderUnavailable(RuntimeError):
    pass
