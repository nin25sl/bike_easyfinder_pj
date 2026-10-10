from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable
from datetime import UTC, datetime

from collection_worker.config import Settings, SourceConfig
from collection_worker.contracts import DiscoveredRecord, DiscoveryPage, Region


class SourceAdapter(ABC):
    def __init__(self, source_key: str, source: SourceConfig, settings: Settings):
        self.source_key = source_key
        self.source = source
        self.settings = settings

    @abstractmethod
    def discover(self, region: Region, limit: int | None = None) -> Iterable[DiscoveredRecord]:
        """Yield records without writing persistence state."""

    def iter_pages(
        self,
        region: Region,
        limit: int | None = None,
        checkpoint: dict | None = None,
    ) -> Iterable[DiscoveryPage]:
        """Default one-page adapter bridge; paged adapters can override it."""
        offset = int((checkpoint or {}).get("offset", 0))
        records: list[DiscoveredRecord] = []
        emitted = 0
        current = 0
        page_number = int((checkpoint or {}).get("page", 0))
        last_item = (checkpoint or {}).get("last_item")
        page_size = self.settings.collection.checkpoint_every
        for record in self.discover(region, limit=None):
            if current < offset:
                current += 1
                continue
            records.append(record)
            last_item = record.source_record_id
            current += 1
            emitted += 1
            if len(records) >= page_size:
                page_number += 1
                yield DiscoveryPage(
                    records=records,
                    checkpoint={
                        "offset": current,
                        "page": page_number,
                        "last_item": last_item,
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                    complete=False,
                )
                records = []
            if limit is not None and emitted >= limit:
                if records:
                    page_number += 1
                yield DiscoveryPage(
                    records=records,
                    checkpoint={
                        "offset": current,
                        "page": page_number,
                        "last_item": last_item,
                        "updated_at": datetime.now(UTC).isoformat(),
                    },
                    complete=True,
                )
                return
        if records:
            page_number += 1
        yield DiscoveryPage(
            records=records,
            checkpoint={
                "offset": current,
                "page": page_number,
                "last_item": last_item,
                "updated_at": datetime.now(UTC).isoformat(),
            },
            complete=True,
        )
