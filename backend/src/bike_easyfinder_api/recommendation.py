from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError, as_completed
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
from .providers import RouteEstimate, RouteProvider


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


def _diversify(candidates: list[RecommendationCandidate]) -> list[RecommendationCandidate]:
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
                    if item.category != result[-1].category and best_score - item.score <= 5
                ),
                None,
            )
            if alternative is not None:
                chosen_index = alternative
        result.append(remaining.pop(chosen_index))
    return result


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
            if len(eligible) == 10:
                break

        estimates, route_failures = self._estimate_routes(request, eligible)
        for spot in eligible:
            route = estimates.get(spot.id)
            if route is None:
                continue

            total = route.outbound_minutes + spot.stay_minutes + route.return_minutes + 15
            if total > request.available_minutes:
                continue
            time_fit = max(0.0, 25.0 * (1 - abs(request.available_minutes - total) / request.available_minutes))
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

        ranked.sort(key=lambda item: (-item.score, item.estimated_total_minutes, str(item.spot_id)))
        return RecommendationResponse(
            recommendation_id=uuid4(),
            generated_at=generated_at,
            recommendation_rule_version=self._rule_version,
            data_version=self._data_version,
            candidates=_diversify(ranked),
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
                except Exception:
                    pass
        except TimeoutError:
            pass
        finally:
            for future in futures:
                future.cancel()
            executor.shutdown(wait=False, cancel_futures=True)
        return estimates, len(spots) - len(estimates)


class RouteProviderUnavailable(RuntimeError):
    pass
