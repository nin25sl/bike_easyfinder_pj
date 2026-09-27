from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable

from collection_worker.config import Settings, SourceConfig
from collection_worker.contracts import DiscoveredRecord, Region


class SourceAdapter(ABC):
    def __init__(self, source_key: str, source: SourceConfig, settings: Settings):
        self.source_key = source_key
        self.source = source
        self.settings = settings

    @abstractmethod
    def discover(self, region: Region, limit: int | None = None) -> Iterable[DiscoveredRecord]:
        """Yield records without writing persistence state."""

