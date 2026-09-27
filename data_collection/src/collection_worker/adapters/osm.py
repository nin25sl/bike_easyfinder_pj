from __future__ import annotations

from collections.abc import Iterable
import json
import time

import httpx

from collection_worker.adapters.base import SourceAdapter
from collection_worker.contracts import DiscoveredRecord, Region
from collection_worker.errors import TemporarySourceError, UnsupportedSourceError
from collection_worker.utils import stable_hash


OSM_FILTER = """
[tourism];
[amenity~\"^(cafe|restaurant|public_bath|parking)$\"];
[leisure~\"^(park|nature_reserve)$\"];
[natural~\"^(peak|beach|hot_spring|cliff)$\"];
[historic];
[place=locality];
"""


class OSMOverpassAdapter(SourceAdapter):
    def discover(self, region: Region, limit: int | None = None) -> Iterable[DiscoveredRecord]:
        west, south, east, north = region.bbox
        bbox = f"{south},{west},{north},{east}"
        selectors = [line.strip().rstrip(";") for line in OSM_FILTER.splitlines() if line.strip()]
        union = "\n".join(f"nwr{selector}({bbox});" for selector in selectors)
        query = f"[out:json][timeout:{self.source.request_timeout_seconds}];({union});out center tags;"
        cache_dir = self.settings.cache_dir / "overpass"
        cache_path = cache_dir / f"{stable_hash(query)}.json"
        cache_ttl = int(self.source.config.get("cache_ttl_seconds", 86400))
        cached = cache_path.is_file() and time.time() - cache_path.stat().st_mtime <= cache_ttl
        response = None
        last_error: Exception | None = None
        if cached:
            decoded = json.loads(cache_path.read_text(encoding="utf-8"))
            response_headers: dict[str, str] = {"x-cache": "hit"}
            response_status = 200
        else:
            for attempt in range(self.settings.openai.max_retries + 1):
                try:
                    response = httpx.post(
                        self.source.base_url or "https://overpass-api.de/api/interpreter",
                        data={"data": query},
                        headers={"User-Agent": str(self.source.config.get("user_agent", "BikeEasyFinder/0.1"))},
                        timeout=self.source.request_timeout_seconds,
                    )
                    if response.status_code == 429 or response.status_code >= 500:
                        retry_after = response.headers.get("retry-after")
                        delay = min(float(retry_after), 60.0) if retry_after and retry_after.isdigit() else min(2 ** attempt, 30)
                        if attempt < self.settings.openai.max_retries:
                            time.sleep(delay)
                            continue
                    response.raise_for_status()
                    break
                except (httpx.HTTPError, ValueError) as exc:
                    last_error = exc
                    if attempt < self.settings.openai.max_retries:
                        time.sleep(min(2 ** attempt, 30))
            if response is None or response.is_error:
                raise TemporarySourceError(f"Overpass request failed: {last_error or response.status_code}")
            decoded = response.json()
            cache_dir.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(json.dumps(decoded, ensure_ascii=False), encoding="utf-8")
            response_headers = {key: value for key, value in response.headers.items() if key.lower() != "set-cookie"}
            response_status = response.status_code
        emitted = 0
        for element in decoded.get("elements", []):
            tags = element.get("tags", {})
            if tags.get("information") in {"guidepost", "board", "map"} and len(tags) <= 2:
                continue
            kind = element.get("type", "unknown")
            osm_id = element.get("id")
            center = element.get("center", {})
            latitude = element.get("lat", center.get("lat"))
            longitude = element.get("lon", center.get("lon"))
            record_id = f"{kind}/{osm_id}"
            yield DiscoveredRecord(
                source_record_id=record_id,
                source_url=f"https://www.openstreetmap.org/{kind}/{osm_id}",
                payload={
                    "source_record_id": record_id,
                    "name": tags.get("name"),
                    "address": tags.get("addr:full"),
                    "latitude": latitude,
                    "longitude": longitude,
                    "opening_hours_text": tags.get("opening_hours"),
                    "parking": "available" if tags.get("parking") or tags.get("amenity") == "parking" else "unknown",
                    "motorcycle_access": "allowed" if tags.get("motorcycle") in {"yes", "designated"} else "unknown",
                    "source_categories": [f"{key}={value}" for key, value in tags.items() if key in {"tourism", "amenity", "leisure", "natural", "historic", "place"}],
                    "features": [],
                    "osm_tags": tags,
                },
                raw_text=__import__("json").dumps(element, ensure_ascii=False),
                content_type="application/json",
                response_headers=response_headers,
                http_status=response_status,
                title=tags.get("name"),
            )
            emitted += 1
            if limit is not None and emitted >= limit:
                return


class OSMPBFAdapter(SourceAdapter):
    def discover(self, region: Region, limit: int | None = None) -> Iterable[DiscoveredRecord]:
        raise UnsupportedSourceError(
            "osm_pbf is the nationwide adapter boundary and requires an extract_path implementation"
        )
