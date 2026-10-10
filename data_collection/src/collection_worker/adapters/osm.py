from __future__ import annotations

import hashlib
import json
import os
import queue
import threading
import time
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path

import httpx

from collection_worker.adapters.base import SourceAdapter
from collection_worker.adapters.osm_common import (
    OSM_TAG_FILTERS,
    osm_record,
    relevant_tags,
)
from collection_worker.contracts import DiscoveredRecord, Region
from collection_worker.errors import (
    ConfigurationError,
    TemporarySourceError,
    UnsupportedSourceError,
)
from collection_worker.utils import stable_hash

OSM_FILTER = "\n".join(
    f"[{key}]" if values is None else f"[{key}~\"^({'|'.join(sorted(values))})$\"]"
    for key, values in OSM_TAG_FILTERS.items()
)

# A collect-all command must use one immutable PBF snapshot even when the
# provider's ``latest`` redirect changes while a long-running batch is in
# progress.  Adapter instances are created per region, so keep the resolved
# extract in process scope for the lifetime of the command.
_PROCESS_EXTRACT_CACHE: dict[str, tuple[Path, dict]] = {}


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
            if not relevant_tags(tags):
                continue
            kind = element.get("type", "unknown")
            osm_id = element.get("id")
            center = element.get("center", {})
            latitude = element.get("lat", center.get("lat"))
            longitude = element.get("lon", center.get("lon"))
            yield osm_record(
                kind, osm_id, tags, latitude, longitude,
                raw_text=json.dumps(element, ensure_ascii=False),
                response_headers=response_headers,
                http_status=response_status,
            )
            emitted += 1
            if limit is not None and emitted >= limit:
                return


class OSMPBFAdapter(SourceAdapter):
    def discover(self, region: Region, limit: int | None = None) -> Iterable[DiscoveredRecord]:
        path, metadata = self._extract()
        try:
            import osmium
        except ImportError as exc:
            raise UnsupportedSourceError("Install the 'osmium' package to use osm_pbf") from exc

        boundary = None
        if region.geometry_wkb:
            from shapely import from_wkb
            from shapely.prepared import prep

            boundary = prep(from_wkb(region.geometry_wkb))
        west, south, east, north = region.bbox
        output: queue.Queue[DiscoveredRecord | BaseException | None] = queue.Queue(maxsize=256)
        stopped = threading.Event()
        pending_areas: dict[tuple[str, int], dict[str, str]] = {}
        emitted_areas: set[tuple[str, int]] = set()
        geometry_factory = osmium.geom.WKBFactory()

        def emit(kind: str, osm_id: int, tags: dict[str, str], lat: float | None, lon: float | None) -> None:
            if stopped.is_set():
                return
            if not relevant_tags(tags):
                return
            if lat is not None and lon is not None:
                if not (west <= lon <= east and south <= lat <= north):
                    return
                if boundary is not None:
                    from shapely.geometry import Point

                    if not boundary.covers(Point(lon, lat)):
                        return
            payload = {"pbf_extract": metadata, "geometry_missing": lat is None or lon is None}
            output.put(osm_record(
                kind, osm_id, tags, lat, lon,
                raw_text=json.dumps(
                    {"type": kind, "id": osm_id, "tags": tags, "lat": lat, "lon": lon},
                    ensure_ascii=False,
                    sort_keys=True,
                ),
                extra_payload=payload,
            ))

        class Handler(osmium.SimpleHandler):
            def node(self, obj):
                tags = {tag.k: tag.v for tag in obj.tags}
                if obj.location.valid():
                    emit("node", obj.id, tags, obj.location.lat, obj.location.lon)

            def way(self, obj):
                tags = {tag.k: tag.v for tag in obj.tags}
                if relevant_tags(tags) and obj.is_closed() and tags.get("area") != "no":
                    key = ("way", obj.id)
                    if key not in emitted_areas:
                        pending_areas[key] = tags
                    return
                points = [(node.lon, node.lat) for node in obj.nodes if node.location.valid()]
                if points:
                    from shapely.geometry import LineString, Point

                    point = LineString(points).representative_point() if len(points) > 1 else Point(points[0])
                    emit("way", obj.id, tags, point.y, point.x)
                elif relevant_tags(tags):
                    emit("way", obj.id, tags, None, None)

            def relation(self, obj):
                tags = {tag.k: tag.v for tag in obj.tags}
                if relevant_tags(tags):
                    key = ("relation", obj.id)
                    if key not in emitted_areas:
                        pending_areas[key] = tags

            def area(self, obj):
                tags = {tag.k: tag.v for tag in obj.tags}
                if not relevant_tags(tags):
                    return
                kind = "way" if obj.from_way() else "relation"
                osm_id = obj.orig_id()
                key = (kind, osm_id)
                try:
                    from shapely.wkb import loads

                    encoded = geometry_factory.create_multipolygon(obj)
                    geometry = loads(encoded, hex=isinstance(encoded, str))
                    point = geometry.representative_point()
                except (RuntimeError, ValueError):
                    pending_areas[key] = tags
                    return
                emitted_areas.add(key)
                pending_areas.pop(key, None)
                emit(kind, osm_id, tags, point.y, point.x)

        def run() -> None:
            try:
                Handler().apply_file(str(path), locations=True)
                for (kind, osm_id), tags in pending_areas.items():
                    if (kind, osm_id) not in emitted_areas:
                        emit(kind, osm_id, tags, None, None)
            except BaseException as exc:  # delivered to the consuming thread
                if not stopped.is_set():
                    output.put(exc)
            finally:
                if not stopped.is_set():
                    output.put(None)

        thread = threading.Thread(target=run, daemon=True)
        thread.start()
        emitted = 0
        while True:
            item = output.get()
            if item is None:
                break
            if isinstance(item, BaseException):
                raise TemporarySourceError(f"Failed to parse PBF: {type(item).__name__}") from item
            yield item
            emitted += 1
            if limit is not None and emitted >= limit:
                stopped.set()
                return

    def _extract(self) -> tuple[Path, dict]:
        configured = self.source.config.get("extract_path")
        if configured:
            path = Path(str(configured))
            if not path.is_file():
                raise ConfigurationError(f"PBF extract not found: {path}")
            return path, {"path": str(path), "managed": False}
        url = str(self.source.config.get("extract_url") or self.source.base_url or "")
        if not url:
            raise ConfigurationError("osm_pbf requires config.extract_path or config.extract_url")
        cached_extract = _PROCESS_EXTRACT_CACHE.get(url)
        if cached_extract is not None and cached_extract[0].is_file():
            return cached_extract
        cache_dir = self.settings.cache_dir / "osm_pbf"
        cache_dir.mkdir(parents=True, exist_ok=True)
        target = cache_dir / (Path(url.split("?", 1)[0]).name or "extract.osm.pbf")
        metadata_path = target.with_suffix(target.suffix + ".json")
        prior = json.loads(metadata_path.read_text(encoding="utf-8")) if metadata_path.is_file() else {}
        headers = {"User-Agent": str(self.source.config.get("user_agent", "BikeEasyFinder/0.1"))}
        if target.is_file() and prior.get("etag"):
            headers["If-None-Match"] = prior["etag"]
        if target.is_file() and prior.get("last_modified"):
            headers["If-Modified-Since"] = prior["last_modified"]
        temp = target.with_suffix(target.suffix + ".part")
        digest = hashlib.sha256()
        try:
            with httpx.stream("GET", url, headers=headers, timeout=self.source.request_timeout_seconds, follow_redirects=True) as response:
                if response.status_code == 304 and target.is_file():
                    result = (target, prior)
                    _PROCESS_EXTRACT_CACHE[url] = result
                    return result
                response.raise_for_status()
                with temp.open("wb") as handle:
                    for chunk in response.iter_bytes():
                        digest.update(chunk)
                        handle.write(chunk)
                metadata = {
                    "url": str(response.url),
                    "etag": response.headers.get("etag"),
                    "last_modified": response.headers.get("last-modified"),
                    "sha256": digest.hexdigest(),
                    "retrieved_at": datetime.now(UTC).isoformat(),
                    "managed": True,
                }
            os.replace(temp, target)
            metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
            result = (target, metadata)
            _PROCESS_EXTRACT_CACHE[url] = result
            return result
        except httpx.HTTPError as exc:
            if target.is_file():
                result = (target, {**prior, "stale_cache": True})
                _PROCESS_EXTRACT_CACHE[url] = result
                return result
            raise TemporarySourceError(f"PBF download failed: {type(exc).__name__}") from exc
        finally:
            if temp.exists():
                temp.unlink()
