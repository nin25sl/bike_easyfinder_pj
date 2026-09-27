"""Apple Maps Server API provider POC runner.

The runner deliberately stores neither credentials nor full API responses.  It
accepts a short-lived Maps access token and writes only measurements needed for
the provider decision.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import os
import statistics
import sys
import time
from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import httpx


API_ROOT = "https://maps-api.apple.com/v1"
PREFECTURES = {
    "fukuoka": (33.5902, 130.4017),
    "saga": (33.2494, 130.2988),
    "nagasaki": (32.7503, 129.8779),
    "kumamoto": (32.8031, 130.7079),
    "oita": (33.2382, 131.6126),
    "miyazaki": (31.9111, 131.4239),
    "kagoshima": (31.5966, 130.5571),
}
SCENARIOS = ("urban", "mountain", "coastal", "highway_allowed", "highway_avoided")


@dataclass(frozen=True)
class RouteCase:
    route_id: str
    prefecture: str
    scenario: str
    origin_lat: float
    origin_lng: float
    destination_lat: float
    destination_lng: float
    highway_allowed: bool
    apple_maps_seconds: int | None


@dataclass(frozen=True)
class Measurement:
    route_id: str
    prefecture: str
    scenario: str
    success: bool
    status_code: int
    latency_ms: float
    expected_seconds: int | None
    distance_meters: int | None
    has_tolls: bool | None
    baseline_seconds: int | None
    relative_error: float | None
    error: str | None


def parse_bool(value: str) -> bool:
    if value.lower() in {"true", "1", "yes"}:
        return True
    if value.lower() in {"false", "0", "no"}:
        return False
    raise ValueError(f"invalid boolean: {value}")


def load_cases(path: Path) -> list[RouteCase]:
    cases: list[RouteCase] = []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            baseline = row.get("apple_maps_seconds", "").strip()
            cases.append(
                RouteCase(
                    route_id=row["route_id"],
                    prefecture=row["prefecture"],
                    scenario=row["scenario"],
                    origin_lat=float(row["origin_lat"]),
                    origin_lng=float(row["origin_lng"]),
                    destination_lat=float(row["destination_lat"]),
                    destination_lng=float(row["destination_lng"]),
                    highway_allowed=parse_bool(row["highway_allowed"]),
                    apple_maps_seconds=int(baseline) if baseline else None,
                )
            )
    validate_cases(cases)
    return cases


def validate_cases(cases: list[RouteCase]) -> None:
    if len({case.route_id for case in cases}) != len(cases):
        raise ValueError("route_id must be unique")
    invalid = [case.route_id for case in cases if case.prefecture not in PREFECTURES]
    if invalid:
        raise ValueError(f"unknown prefecture in: {', '.join(invalid[:5])}")
    for case in cases:
        if not (-90 <= case.origin_lat <= 90 and -90 <= case.destination_lat <= 90):
            raise ValueError(f"invalid latitude: {case.route_id}")
        if not (-180 <= case.origin_lng <= 180 and -180 <= case.destination_lng <= 180):
            raise ValueError(f"invalid longitude: {case.route_id}")


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    index = max(0, math.ceil(percentile * len(ordered)) - 1)
    return ordered[index]


def _request_case(client: httpx.Client, case: RouteCase) -> Measurement:
    # /v1/etas has no avoid option. Highway-avoided cases therefore use
    # /v1/directions, whose avoid=Highways contract must be verified by the POC.
    if case.highway_allowed:
        endpoint = "/etas"
        params: dict[str, str] = {
            "origin": f"{case.origin_lat},{case.origin_lng}",
            "destinations": f"{case.destination_lat},{case.destination_lng}",
            "transportType": "Automobile",
        }
    else:
        endpoint = "/directions"
        params = {
            "origin": f"{case.origin_lat},{case.origin_lng}",
            "destination": f"{case.destination_lat},{case.destination_lng}",
            "transportType": "Automobile",
            "avoid": "Highways",
            "requestsAlternateRoutes": "false",
        }

    started = time.perf_counter()
    try:
        response = client.get(endpoint, params=params)
        latency_ms = (time.perf_counter() - started) * 1000
        response.raise_for_status()
        body = response.json()
        if endpoint == "/etas":
            item = body["etas"][0]
            seconds = int(item["expectedTravelTimeSeconds"])
            distance = int(item["distanceMeters"])
            has_tolls = None
        else:
            item = body["routes"][0]
            seconds = int(item["durationSeconds"])
            distance = int(item["distanceMeters"])
            has_tolls = item.get("hasTolls")
        relative_error = (
            abs(seconds - case.apple_maps_seconds) / case.apple_maps_seconds
            if case.apple_maps_seconds
            else None
        )
        return Measurement(
            case.route_id, case.prefecture, case.scenario, True, response.status_code,
            round(latency_ms, 2), seconds, distance, has_tolls,
            case.apple_maps_seconds, relative_error, None,
        )
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError) as exc:
        status = getattr(getattr(exc, "response", None), "status_code", 0)
        return Measurement(
            case.route_id, case.prefecture, case.scenario, False, status,
            round((time.perf_counter() - started) * 1000, 2), None, None, None,
            case.apple_maps_seconds, None, type(exc).__name__,
        )


def run(cases: Iterable[RouteCase], token: str, timeout_seconds: float = 4.0) -> list[Measurement]:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    with httpx.Client(base_url=API_ROOT, headers=headers, timeout=timeout_seconds) as client:
        return [_request_case(client, case) for case in cases]


def summarize(cases: list[RouteCase], results: list[Measurement]) -> dict[str, Any]:
    success_count = sum(item.success for item in results)
    errors = [item.relative_error for item in results if item.relative_error is not None]
    latencies = [item.latency_ms for item in results if item.success]
    counts = Counter(case.prefecture for case in cases)
    avoided = [item for item in results if item.scenario == "highway_avoided" and item.success]
    baseline_complete = len(errors) == len(cases)
    gates = {
        "coverage_7_prefectures_20_each": len(cases) >= 140 and all(counts[p] >= 20 for p in PREFECTURES),
        "success_rate_99pct": bool(cases) and success_count / len(cases) >= 0.99,
        "eta_median_error_15pct": baseline_complete and statistics.median(errors) <= 0.15,
        "eta_p95_error_30pct": baseline_complete and (_percentile(errors, 0.95) or 1) <= 0.30,
        # hasTolls is the only machine-readable route flag. Final highway avoidance
        # still requires visual comparison with Apple Maps and route geometry.
        "avoided_route_tolls_zero": bool(avoided) and all(item.has_tolls is False for item in avoided),
        "single_call_latency_p95_under_4s": bool(latencies) and (_percentile(latencies, 0.95) or 4001) <= 4000,
        "manual_highway_and_asymmetry_review": False,
        "privacy_terms_quota_review": False,
    }
    return {
        "case_count": len(cases),
        "success_count": success_count,
        "success_rate": success_count / len(cases) if cases else 0,
        "baseline_complete": baseline_complete,
        "median_relative_error": statistics.median(errors) if errors else None,
        "p95_relative_error": _percentile(errors, 0.95),
        "p95_latency_ms": _percentile(latencies, 0.95),
        "prefecture_counts": dict(sorted(counts.items())),
        "gates": gates,
        "decision": "PASS" if all(gates.values()) else "PENDING_OR_FAIL",
    }


def write_jsonl(path: Path, results: list[Measurement]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for item in results:
            handle.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")


def generate_template(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "route_id", "prefecture", "scenario", "origin_lat", "origin_lng",
        "destination_lat", "destination_lng", "highway_allowed", "apple_maps_seconds",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for prefecture, (lat, lng) in PREFECTURES.items():
            for index in range(20):
                scenario = SCENARIOS[index % len(SCENARIOS)]
                ring = index // len(SCENARIOS) + 1
                angle = math.radians((index * 137.5) % 360)
                writer.writerow({
                    "route_id": f"{prefecture}-{index + 1:02d}",
                    "prefecture": prefecture,
                    "scenario": scenario,
                    "origin_lat": f"{lat:.6f}",
                    "origin_lng": f"{lng:.6f}",
                    "destination_lat": f"{lat + 0.08 * ring * math.sin(angle):.6f}",
                    "destination_lng": f"{lng + 0.10 * ring * math.cos(angle):.6f}",
                    "highway_allowed": str(scenario != "highway_avoided").lower(),
                    "apple_maps_seconds": "",
                })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=Path("config/apple_maps_poc_routes.csv"))
    parser.add_argument("--output", type=Path, default=Path("output/apple_maps_poc_results.jsonl"))
    parser.add_argument("--summary", type=Path, default=Path("output/apple_maps_poc_summary.json"))
    parser.add_argument("--generate-template", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.generate_template:
        generate_template(args.cases)
        print(f"generated {args.cases}")
        return 0
    cases = load_cases(args.cases)
    if args.dry_run:
        print(json.dumps({"case_count": len(cases), "valid": True}, ensure_ascii=False))
        return 0
    token = os.environ.get("APPLE_MAPS_ACCESS_TOKEN", "").strip()
    if not token:
        print("APPLE_MAPS_ACCESS_TOKEN is required", file=sys.stderr)
        return 2
    results = run(cases, token)
    summary = summarize(cases, results)
    write_jsonl(args.output, results)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0 if summary["decision"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
