from datetime import UTC, datetime
from uuid import UUID

from bike_easyfinder_api.contracts import Coordinate, RecommendationRequest
from bike_easyfinder_api.providers import ApproximateRouteProvider
from bike_easyfinder_api.recommendation import (
    RecommendationEngine,
    Spot,
    search_radius_km,
)


def make_spot(
    identifier: int,
    category: str,
    tags: tuple[str, ...],
    latitude: float = 33.6,
    stay_minutes: int = 20,
) -> Spot:
    return Spot(
        id=UUID(f"00000000-0000-0000-0000-{identifier:012d}"),
        name=f"spot-{identifier}",
        summary=None,
        category=category,
        tags=tags,
        coordinate=Coordinate(latitude=latitude, longitude=130.4),
        stay_minutes=stay_minutes,
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


def test_engine_filters_by_target_time_window_and_returns_contract_versions() -> None:
    engine = RecommendationEngine(ApproximateRouteProvider(), "mvp-1.1", "test-data")
    response = engine.recommend(
        request(),
        [
            make_spot(1, "coast", ("sea",), 33.61, stay_minutes=97),
            make_spot(2, "mountain", ("mountain",), 34.5),
        ],
    )
    assert response.recommendation_rule_version == "mvp-1.1"
    assert response.data_version == "test-data"
    assert [candidate.spot_id for candidate in response.candidates] == [
        make_spot(1, "coast", ("sea",)).id
    ]
    assert response.candidates[0].route.profile == "auto"
    assert response.candidates[0].return_buffer_minutes == 15


def test_negative_reaction_lowers_the_matching_spot() -> None:
    engine = RecommendationEngine(ApproximateRouteProvider(), "mvp-1.1", "test")
    first = make_spot(1, "coast", ("sea",), stay_minutes=97)
    second = make_spot(2, "coast", ("sea",), stay_minutes=97)
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
            make_spot(2, "coast", ("sea",), stay_minutes=97),
            make_spot(3, "mountain", ("mountain",), stay_minutes=97),
        ],
    )
    assert response.candidates[0].category == "coast"
    assert response.candidates[1].category == "mountain"


def test_four_hour_request_returns_only_plus_or_minus_fifteen_minutes() -> None:
    engine = RecommendationEngine(ApproximateRouteProvider(), "mvp-1.2", "test")
    response = engine.recommend(
        request(available_minutes=240, interests=["any"]),
        [
            make_spot(1, "coast", ("sea",), stay_minutes=205),
            make_spot(2, "mountain", ("mountain",), stay_minutes=220),
            make_spot(3, "cafe", ("cafe",), stay_minutes=20),
        ],
    )

    assert response.candidates
    assert all(abs(candidate.estimated_total_minutes - 240) <= 15 for candidate in response.candidates)
    assert not response.warnings


def test_time_window_expands_in_fifteen_minute_steps() -> None:
    engine = RecommendationEngine(ApproximateRouteProvider(), "mvp-1.2", "test")
    response = engine.recommend(
        request(available_minutes=240, interests=["any"]),
        [make_spot(1, "coast", ("sea",), stay_minutes=195)],
    )

    assert len(response.candidates) == 1
    assert abs(response.candidates[0].estimated_total_minutes - 240) <= 30
    assert response.warnings[0].code == "TIME_WINDOW_EXPANDED"
    assert "±30分" in response.warnings[0].message


def test_preselection_is_not_limited_to_first_ten_nearby_spots() -> None:
    engine = RecommendationEngine(ApproximateRouteProvider(), "mvp-1.2", "test")
    nearby_short_spots = [
        make_spot(index, "coast", ("sea",), stay_minutes=20) for index in range(1, 11)
    ]
    target_fit = make_spot(11, "mountain", ("mountain",), stay_minutes=215)

    response = engine.recommend(
        request(available_minutes=240, interests=["any"]),
        nearby_short_spots + [target_fit],
    )

    assert [candidate.spot_id for candidate in response.candidates] == [target_fit.id]

