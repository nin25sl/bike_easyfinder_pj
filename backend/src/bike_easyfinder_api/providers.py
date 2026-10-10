from __future__ import annotations

import math
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID
from typing import Protocol

import httpx
from sqlalchemy import Engine, text

from .contracts import Coordinate


@dataclass(frozen=True)
class RouteEstimate:
    outbound_minutes: int
    return_minutes: int
    distance_km: float
    encoded_polyline: str
    generated_at: datetime


class RouteProvider(Protocol):
    name: str

    def estimate(
        self,
        origin: Coordinate,
        destination: Coordinate,
        *,
        allow_highway: bool,
        spot_id: UUID | None = None,
        stay_minutes: int = 0,
    ) -> RouteEstimate: ...


def haversine_km(origin: Coordinate, destination: Coordinate) -> float:
    radius = 6371.0088
    lat1, lat2 = math.radians(origin.latitude), math.radians(destination.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(destination.longitude - origin.longitude)
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _encode_polyline6(points: list[tuple[float, float]]) -> str:
    output: list[str] = []
    previous_lat = previous_lon = 0
    for latitude, longitude in points:
        lat = round(latitude * 1_000_000)
        lon = round(longitude * 1_000_000)
        for delta in (lat - previous_lat, lon - previous_lon):
            value = ~(delta << 1) if delta < 0 else delta << 1
            while value >= 0x20:
                output.append(chr((0x20 | (value & 0x1F)) + 63))
                value >>= 5
            output.append(chr(value + 63))
        previous_lat, previous_lon = lat, lon
    return "".join(output)


class ApproximateRouteProvider:
    """Deterministic local/test provider. It is deliberately forbidden in shared environments."""

    name = "approximate-local"

    def estimate(
        self,
        origin: Coordinate,
        destination: Coordinate,
        *,
        allow_highway: bool,
        spot_id: UUID | None = None,
        stay_minutes: int = 0,
    ) -> RouteEstimate:
        direct_km = haversine_km(origin, destination)
        road_km = direct_km * 1.22
        average_kph = 55 if allow_highway else 42
        one_way = max(1, math.ceil(road_km / average_kph * 60))
        return RouteEstimate(
            outbound_minutes=one_way,
            return_minutes=one_way,
            distance_km=round(road_km * 2, 1),
            encoded_polyline=_encode_polyline6(
                [(origin.latitude, origin.longitude), (destination.latitude, destination.longitude)]
            ),
            generated_at=datetime.now(UTC),
        )


class AppleMapsRouteProvider:
    """Apple Maps Server API adapter; secrets stay on the server."""

    name = "apple-maps"

    def __init__(self, token: str, endpoint: str, timeout_seconds: float = 3.5) -> None:
        self._token = token
        self._endpoint = endpoint
        self._timeout = timeout_seconds

    def estimate(
        self,
        origin: Coordinate,
        destination: Coordinate,
        *,
        allow_highway: bool,
        spot_id: UUID | None = None,
        stay_minutes: int = 0,
    ) -> RouteEstimate:
        outbound = self._fetch_route(origin, destination, allow_highway=allow_highway)
        return_departure = datetime.now(UTC) + timedelta(
            minutes=outbound[0] + stay_minutes
        )
        inbound = self._fetch_route(
            destination,
            origin,
            allow_highway=allow_highway,
            departure_date=return_departure,
        )
        return RouteEstimate(
            outbound_minutes=outbound[0],
            return_minutes=inbound[0],
            distance_km=round(outbound[1] + inbound[1], 1),
            encoded_polyline=outbound[2],
            generated_at=datetime.now(UTC),
        )

    def _fetch_route(
        self,
        origin: Coordinate,
        destination: Coordinate,
        *,
        allow_highway: bool,
        departure_date: datetime | None = None,
    ) -> tuple[int, float, str]:
        params: dict[str, str] = {
            "origin": f"{origin.latitude},{origin.longitude}",
            "destination": f"{destination.latitude},{destination.longitude}",
            "transportType": "Automobile",
        }
        if not allow_highway:
            params["avoid"] = "Highways"
        if departure_date:
            params["departureDate"] = departure_date.isoformat().replace("+00:00", "Z")
        response = httpx.get(
            self._endpoint,
            params=params,
            headers={"Authorization": f"Bearer {self._token}"},
            timeout=self._timeout,
        )
        response.raise_for_status()
        payload = response.json()
        routes = payload.get("routes") or []
        if not routes:
            raise RuntimeError("Apple Maps returned no routes")
        route = routes[0]
        seconds = float(route["durationSeconds"])
        distance_meters = float(route["distanceMeters"])
        points: list[tuple[float, float]] = []
        steps = payload.get("steps") or []
        step_paths = payload.get("stepPaths") or []
        for step_index in route.get("stepIndexes") or []:
            if step_index >= len(steps):
                continue
            path_index = steps[step_index].get("stepPathIndex")
            if path_index is None or path_index >= len(step_paths):
                continue
            path = step_paths[path_index]
            if isinstance(path, dict):
                path = path.get("points") or path.get("path") or []
            for point in path:
                if isinstance(point, dict) and "latitude" in point and "longitude" in point:
                    points.append((float(point["latitude"]), float(point["longitude"])))
        if not points:
            points = [(origin.latitude, origin.longitude), (destination.latitude, destination.longitude)]
        one_way = max(1, math.ceil(seconds / 60))
        return one_way, distance_meters / 1000, _encode_polyline6(points)


class DatabaseCachingRouteProvider:
    """15-minute route cache using an approximately 1km origin mesh."""

    def __init__(self, engine: Engine, wrapped: RouteProvider, ttl_minutes: int = 15) -> None:
        self._engine = engine
        self._wrapped = wrapped
        self._ttl = timedelta(minutes=ttl_minutes)
        self.name = f"cached-{wrapped.name}"

    def estimate(
        self,
        origin: Coordinate,
        destination: Coordinate,
        *,
        allow_highway: bool,
        spot_id: UUID | None = None,
        stay_minutes: int = 0,
    ) -> RouteEstimate:
        if spot_id is None:
            return self._wrapped.estimate(
                origin,
                destination,
                allow_highway=allow_highway,
                spot_id=spot_id,
                stay_minutes=stay_minutes,
            )
        now = datetime.now(UTC)
        bucket = int(now.timestamp() // (15 * 60))
        identity = {
            "origin_lat": round(origin.latitude, 2),
            "origin_lon": round(origin.longitude, 2),
            "spot_id": str(spot_id),
            "direction": "roundtrip",
            "allow_highway": allow_highway,
            "stay_minutes": stay_minutes,
            "bucket": bucket,
            "provider": self._wrapped.name,
        }
        key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
        with self._engine.connect() as connection:
            row = connection.execute(
                text(
                    """
                    SELECT outbound_minutes, return_minutes, distance_km,
                           encoded_polyline, generated_at
                    FROM route_estimate_cache
                    WHERE cache_key=:key AND expires_at > now()
                    """
                ),
                {"key": key},
            ).mappings().first()
        if row:
            return RouteEstimate(
                outbound_minutes=row["outbound_minutes"],
                return_minutes=row["return_minutes"],
                distance_km=float(row["distance_km"]),
                encoded_polyline=row["encoded_polyline"],
                generated_at=row["generated_at"],
            )

        result = self._wrapped.estimate(
            origin,
            destination,
            allow_highway=allow_highway,
            spot_id=spot_id,
            stay_minutes=stay_minutes,
        )
        with self._engine.begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO route_estimate_cache(
                        cache_key, spot_id, provider, outbound_minutes, return_minutes,
                        distance_km, encoded_polyline, generated_at, expires_at
                    ) VALUES (
                        :key, :spot_id, :provider, :outbound, :return_minutes,
                        :distance, :polyline, :generated_at, :expires_at
                    ) ON CONFLICT (cache_key) DO UPDATE SET
                        outbound_minutes=EXCLUDED.outbound_minutes,
                        return_minutes=EXCLUDED.return_minutes,
                        distance_km=EXCLUDED.distance_km,
                        encoded_polyline=EXCLUDED.encoded_polyline,
                        generated_at=EXCLUDED.generated_at,
                        expires_at=EXCLUDED.expires_at
                    """
                ),
                {
                    "key": key,
                    "spot_id": spot_id,
                    "provider": self._wrapped.name,
                    "outbound": result.outbound_minutes,
                    "return_minutes": result.return_minutes,
                    "distance": result.distance_km,
                    "polyline": result.encoded_polyline,
                    "generated_at": result.generated_at,
                    "expires_at": result.generated_at + self._ttl,
                },
            )
        return result
