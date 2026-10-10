import hashlib
from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.testclient import TestClient

from bike_easyfinder_api.config import Settings
from bike_easyfinder_api.contracts import Coordinate
from bike_easyfinder_api.main import create_app
from bike_easyfinder_api.providers import ApproximateRouteProvider
from bike_easyfinder_api.recommendation import RecommendationEngine, Spot


class FakeRepository:
    def __init__(self) -> None:
        self.deleted: list[UUID] = []
        self.events = 0

    def nearby_spots(self, origin: Coordinate, radius_km: float):
        return [
            Spot(
                id=UUID("00000000-0000-0000-0000-000000000001"),
                name="海岸展望所",
                summary="テスト候補",
                category="coast",
                tags=("sea", "scenic"),
                coordinate=Coordinate(latitude=33.61, longitude=130.4),
                stay_minutes=20,
                confidence=0.9,
                popularity_score=5,
                verified_at=datetime.now(UTC),
            )
        ]

    def record_interactions(self, installation_id, token_hash, batch):
        self.events += len(batch.events)
        return len(batch.events)

    def request_deletion(self, installation_id, raw_token):
        self.deleted.append(installation_id)


def client_and_repository():
    repository = FakeRepository()
    app = create_app(
        Settings(app_env="test", database_url="postgresql+psycopg://unused"),
        repository=repository,
        engine=RecommendationEngine(ApproximateRouteProvider(), "mvp-1.1", "test-data"),
    )
    return TestClient(app), repository


def test_recommendation_endpoint() -> None:
    client, _ = client_and_repository()
    response = client.post(
        "/v1/recommendations",
        json={
            "origin": {"latitude": 33.59, "longitude": 130.4},
            "available_minutes": 120,
            "interests": ["sea"],
            "allow_highway": False,
        },
    )
    assert response.status_code == 200
    assert response.json()["candidates"][0]["name"] == "海岸展望所"
    assert response.headers["x-request-id"]


def test_interactions_require_installation_headers() -> None:
    client, _ = client_and_repository()
    response = client.post("/v1/interactions", json={"events": []})
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


def test_interaction_batch_over_50_returns_413() -> None:
    client, _ = client_and_repository()
    installation_id = uuid4()
    event = {
        "event_id": str(uuid4()),
        "session_id": str(uuid4()),
        "recommendation_id": str(uuid4()),
        "spot_id": "00000000-0000-0000-0000-000000000001",
        "event_type": "shown",
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    events = [{**event, "event_id": str(uuid4())} for _ in range(51)]
    response = client.post(
        "/v1/interactions",
        headers={
            "X-Installation-ID": str(installation_id),
            "X-Deletion-Token-Hash": "a" * 64,
        },
        json={"events": events},
    )
    assert response.status_code == 413


def test_interactions_and_privacy_neutral_deletion() -> None:
    client, repository = client_and_repository()
    installation_id = uuid4()
    token = "a" * 32
    event = {
        "event_id": str(uuid4()),
        "session_id": str(uuid4()),
        "recommendation_id": str(uuid4()),
        "spot_id": "00000000-0000-0000-0000-000000000001",
        "event_type": "shown",
        "occurred_at": datetime.now(UTC).isoformat(),
    }
    response = client.post(
        "/v1/interactions",
        headers={
            "X-Installation-ID": str(installation_id),
            "X-Deletion-Token-Hash": hashlib.sha256(token.encode()).hexdigest(),
        },
        json={"events": [event]},
    )
    assert response.status_code == 202
    assert response.json() == {"accepted": 1}

    deletion = client.delete(
        f"/v1/installations/{installation_id}/data",
        headers={"X-Deletion-Token": token},
    )
    assert deletion.status_code == 202
    assert repository.deleted == [installation_id]
