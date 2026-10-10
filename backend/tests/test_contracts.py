import pytest
from pydantic import ValidationError

from bike_easyfinder_api.config import Settings
from bike_easyfinder_api.contracts import RecommendationRequest


def test_preference_weight_range_is_enforced() -> None:
    with pytest.raises(ValidationError):
        RecommendationRequest.model_validate(
            {
                "origin": {"latitude": 33.5, "longitude": 130.4},
                "available_minutes": 120,
                "interests": ["any"],
                "allow_highway": False,
                "preference_profile": {"tag_weights": {"sea": 16}},
            }
        )


def test_shared_environment_rejects_approximate_routes() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="staging", route_provider="approximate")


def test_apple_provider_requires_token() -> None:
    with pytest.raises(ValidationError):
        Settings(app_env="staging", route_provider="apple", apple_maps_access_token=None)
