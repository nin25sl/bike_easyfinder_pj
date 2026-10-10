from __future__ import annotations

import csv
import json
from collections.abc import Iterable
from pathlib import Path

from collection_worker.adapters.base import SourceAdapter
from collection_worker.contracts import DiscoveredRecord, Region
from collection_worker.errors import ConfigurationError


class ManualSeedAdapter(SourceAdapter):
    def discover(self, region: Region, limit: int | None = None) -> Iterable[DiscoveredRecord]:
        emitted = 0
        for configured in self.source.config.get("paths", []):
            path = Path(configured)
            if not path.exists():
                continue
            if path.suffix.lower() == ".jsonl":
                records = (
                    json.loads(line)
                    for line in path.read_text(encoding="utf-8").splitlines()
                    if line.strip()
                )
            elif path.suffix.lower() == ".csv":
                records = csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines())
            else:
                raise ConfigurationError(f"Unsupported manual seed format: {path}")
            for payload in records:
                if payload.get("region_code") and not self._matches_region(
                    str(payload["region_code"]), region
                ):
                    continue
                source_url = payload.get("source_url")
                source_record_id = payload.get("source_record_id")
                if not source_url or not source_record_id:
                    raise ConfigurationError(f"Manual seed requires source_url and source_record_id: {path}")
                yield DiscoveredRecord(
                    source_record_id=str(source_record_id),
                    source_url=str(source_url),
                    payload=dict(payload),
                    content_type="application/json",
                    title=payload.get("name"),
                )
                emitted += 1
                if limit is not None and emitted >= limit:
                    return

    @staticmethod
    def _matches_region(record_region_code: str, region: Region) -> bool:
        if region.region_kind == "prefecture":
            return record_region_code.startswith(region.prefecture_code)
        return record_region_code == region.region_code
