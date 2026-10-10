from datetime import UTC, datetime
from uuid import uuid4

import httpx

from bike_easyfinder_api.contracts import Coordinate
from bike_easyfinder_api.providers import AppleMapsRouteProvider


class FakeResponse:
    status_code = 200

    def __init__(self, duration: int, distance: int) -> None:
        self._payload = {
            "routes": [
                {
                    "durationSeconds": duration,
                    "distanceMeters": distance,
                    "stepIndexes": [0],
                }
            ],
            "steps": [{"stepPathIndex": 0}],
            "stepPaths": [
                [
                    {"latitude": 33.5, "longitude": 130.4},
                    {"latitude": 33.6, "longitude": 130.5},
                ]
            ],
        }

    def raise_for_status(self) -> None:
        return None

    def json(self):
        return self._payload


def test_apple_provider_requests_outbound_and_future_return(monkeypatch) -> None:
    calls: list[dict] = []

    def fake_get(url, *, params, headers, timeout):
        calls.append(params)
        return FakeResponse(601 if len(calls) == 1 else 721, 10_000)

    monkeypatch.setattr(httpx, "get", fake_get)
    provider = AppleMapsRouteProvider("secret", "https://maps-api.apple.com/v1/directions")
    result = provider.estimate(
        Coordinate(latitude=33.5, longitude=130.4),
        Coordinate(latitude=33.6, longitude=130.5),
        allow_highway=False,
        spot_id=uuid4(),
        stay_minutes=30,
    )

    assert result.outbound_minutes == 11
    assert result.return_minutes == 13
    assert result.distance_km == 20
    assert result.encoded_polyline
    assert calls[0]["avoid"] == "Highways"
    assert "departureDate" not in calls[0]
    assert calls[1]["departureDate"].endswith("Z")

