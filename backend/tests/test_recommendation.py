from datetime import UTC, datetime
from uuid import UUID

from bike_easyfinder_api.contracts import Coordinate, RecommendationRequest
from bike_easyfinder_api.providers import ApproximateRouteProvider
from bike_easyfinder_api.recommendation import RecommendationEngine, Spot, search_radius_km


def make_spot(identifier: int, category: str, tags: tuple[str, ...], latitude: float = 33.6) -> Spot:
    return Spot(
        id=UUID(f"00000000-0000-0000-0000-{identifier:012d}"),
        name=f"spot-{identifier}",
        summary=None,
        category=category,
        tags=tags,
        coordinate=Coordinate(latitude=latitude, longitude=130.4),
        stay_minutes=20,
        confidence=0.9,
        popularity_score=5,
        verified_at=datetime.now(UTC),
    )


def request(**overrides) -> RecommendationRequest:
    values = {
        "origin": {"latitude": 33.59, "longitude": 130.4},
        "available_minutes": 120,
        "interests": ["sea"],
        "allow_highway": False,
    }
    values.update(overrides)
    return RecommendationRequest.model_validate(values)


def test_search_radius_is_capped_at_250km() -> None:
    assert search_radius_km(60) == 90
    assert search_radius_km(600) == 250


def test_engine_hard_filters_by_total_time_and_returns_contract_versions() -> None:
    engine = RecommendationEngine(ApproximateRouteProvider(), "mvp-1.1", "test-data")
    response = engine.recommend(
        request(),
        [
            make_spot(1, "coast", ("sea",), 33.61),
            make_spot(2, "mountain", ("mountain",), 34.5),
        ],
    )
    assert response.recommendation_rule_version == "mvp-1.1"
    assert response.data_version == "test-data"
    assert [candidate.spot_id for candidate in response.candidates] == [make_spot(1, "coast", ("sea",)).id]
    assert response.candidates[0].route.profile == "auto"
    assert response.candidates[0].return_buffer_minutes == 15


def test_negative_reaction_lowers_the_matching_spot() -> None:
    engine = RecommendationEngine(ApproximateRouteProvider(), "mvp-1.1", "test")
    first = make_spot(1, "coast", ("sea",))
    second = make_spot(2, "coast", ("sea",))
    response = engine.recommend(
        request(
            preference_profile={
                "spot_reactions": [{"spot_id": str(first.id), "reaction": "not_interested"}]
            }
        ),
        [first, second],
    )
    assert response.candidates[0].spot_id == second.id


def test_diversity_promotes_close_scoring_different_category() -> None:
    engine = RecommendationEngine(ApproximateRouteProvider(), "mvp-1.1", "test")
    response = engine.recommend(
        request(interests=["any"]),
        [
            make_spot(1, "coast", ("sea",)),
            make_spot(2, "coast", ("sea",)),
            make_spot(3, "mountain", ("mountain",)),
        ],
    )
    assert response.candidates[0].category == "coast"
    assert response.candidates[1].category == "mountain"

