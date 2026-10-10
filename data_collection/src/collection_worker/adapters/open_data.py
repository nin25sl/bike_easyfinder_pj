from __future__ import annotations

import csv
import hashlib
import io
import json
import time
from collections.abc import Iterable

from collection_worker.adapters.base import SourceAdapter
from collection_worker.contracts import DiscoveredRecord, Region
from collection_worker.errors import PermanentSourceError
from collection_worker.http import domain_of, fetch_url
from collection_worker.utils import stable_hash


class OpenDataAdapter(SourceAdapter):
    def discover(self, region: Region, limit: int | None = None) -> Iterable[DiscoveredRecord]:
        emitted = 0
        last_request = 0.0
        minimum_interval = 60.0 / self.source.rate_limit_per_minute
        datasets = self.source.config.get("datasets", [])[: self.source.max_pages_per_run]
        for dataset in datasets:
            allowed_regions = [str(item) for item in dataset.get("region_codes", [])]
            if allowed_regions and region.region_code not in allowed_regions and region.prefecture_code not in allowed_regions:
                continue
            url = str(dataset["url"])
            delay = minimum_interval - (time.monotonic() - last_request)
            if delay > 0:
                time.sleep(delay)
            result = fetch_url(
                url,
                allowed_domain=domain_of(url),
                timeout_seconds=self.source.request_timeout_seconds,
                max_bytes=self.settings.collection.max_response_bytes,
                headers={"User-Agent": str(dataset.get("user_agent", "BikeEasyFinder/0.1"))},
                max_retries=self.settings.openai.max_retries,
            )
            last_request = time.monotonic()
            data_format = str(dataset.get("format", "json")).lower()
            records = self._records(data_format, result.content, str(dataset.get("encoding", "utf-8-sig")))
            expected = set(dataset.get("expected_columns", []))
            actual = set(records[0]) if records else set()
            missing = expected - actual
            if missing:
                raise PermanentSourceError(
                    f"Dataset {dataset.get('dataset_id', url)} is missing columns: {', '.join(sorted(missing))}"
                )
            mapping = dataset.get("mapping", {})
            seen_ids: set[str] = set()
            for index, original in enumerate(records):
                payload = self._map_record(original, mapping)
                if payload.get("region_code") and str(payload["region_code"]) != region.region_code:
                    continue
                id_fields = dataset.get("id_fields") or [dataset.get("id_field", "id")]
                identity_parts = [str(original.get(field, "")).strip() for field in id_fields]
                identity = "|".join(identity_parts) if any(identity_parts) else ""
                record_id = str(payload.get("source_record_id") or identity or stable_hash(
                    result.url, str(index), json.dumps(original, ensure_ascii=False, sort_keys=True)
                ))
                if record_id in seen_ids:
                    raise PermanentSourceError(
                        f"Dataset {dataset.get('dataset_id', url)} contains duplicate id: {record_id}"
                    )
                seen_ids.add(record_id)
                yield DiscoveredRecord(
                    source_record_id=record_id,
                    source_url=str(payload.get("source_url") or result.url),
                    payload={
                        **payload,
                        "_source_payload": original,
                        "_dataset_id": dataset.get("dataset_id"),
                        "_dataset_updated_at": dataset.get("updated_at"),
                        "_content_sha256": hashlib.sha256(result.content).hexdigest(),
                    },
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
    def _records(data_format: str, content: bytes, encoding: str = "utf-8-sig") -> list[dict]:
        if data_format == "csv":
            return list(csv.DictReader(io.StringIO(content.decode(encoding))))
        decoded = json.loads(content.decode(encoding))
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
