from __future__ import annotations

import csv
import io
import json
from collections.abc import Iterable

from collection_worker.adapters.base import SourceAdapter
from collection_worker.contracts import DiscoveredRecord, Region
from collection_worker.http import domain_of, fetch_url
from collection_worker.utils import stable_hash


class OpenDataAdapter(SourceAdapter):
    def discover(self, region: Region, limit: int | None = None) -> Iterable[DiscoveredRecord]:
        emitted = 0
        datasets = self.source.config.get("datasets", [])[: self.source.max_pages_per_run]
        for dataset in datasets:
            url = str(dataset["url"])
            result = fetch_url(
                url,
                allowed_domain=domain_of(url),
                timeout_seconds=self.source.request_timeout_seconds,
                max_bytes=self.settings.collection.max_response_bytes,
                headers={"User-Agent": str(dataset.get("user_agent", "BikeEasyFinder/0.1"))},
                max_retries=self.settings.openai.max_retries,
            )
            data_format = str(dataset.get("format", "json")).lower()
            records = self._records(data_format, result.content)
            mapping = dataset.get("mapping", {})
            for index, original in enumerate(records):
                payload = self._map_record(original, mapping)
                if payload.get("region_code") and str(payload["region_code"]) != region.region_code:
                    continue
                record_id = str(
                    payload.get("source_record_id")
                    or original.get(dataset.get("id_field", "id"))
                    or stable_hash(result.url, str(index), json.dumps(original, ensure_ascii=False, sort_keys=True))
                )
                yield DiscoveredRecord(
                    source_record_id=record_id,
                    source_url=str(payload.get("source_url") or result.url),
                    payload={**payload, "_source_payload": original},
                    raw_text=json.dumps(original, ensure_ascii=False),
                    content_type=result.headers.get("content-type", "application/json"),
                    response_headers=result.headers,
                    http_status=result.status_code,
                    title=payload.get("name"),
                )
                emitted += 1
                if limit is not None and emitted >= limit:
                    return

    @staticmethod
    def _records(data_format: str, content: bytes) -> list[dict]:
        if data_format == "csv":
            return list(csv.DictReader(io.StringIO(content.decode("utf-8-sig"))))
        decoded = json.loads(content)
        if data_format == "geojson":
            return [
                {
                    **feature.get("properties", {}),
                    "geometry": feature.get("geometry"),
                }
                for feature in decoded.get("features", [])
            ]
        if isinstance(decoded, list):
            return decoded
        return decoded.get("results") or decoded.get("items") or decoded.get("data") or []

    @staticmethod
    def _map_record(original: dict, mapping: dict) -> dict:
        payload = {target: original.get(source) for target, source in mapping.items()}
        geometry = original.get("geometry")
        if geometry and geometry.get("type") == "Point":
            payload.setdefault("longitude", geometry["coordinates"][0])
            payload.setdefault("latitude", geometry["coordinates"][1])
        return payload
