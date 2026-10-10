from collection_worker.adapters.base import SourceAdapter
from collection_worker.adapters.manual import ManualSeedAdapter
from collection_worker.adapters.open_data import OpenDataAdapter
from collection_worker.adapters.openai_discovery import OpenAIDiscoveryAdapter
from collection_worker.adapters.osm import OSMOverpassAdapter, OSMPBFAdapter
from collection_worker.adapters.web import (
    GeneralWebAdapter,
    OfficialWebAdapter,
    TouringMediaAdapter,
)

__all__ = [
    "GeneralWebAdapter",
    "ManualSeedAdapter",
    "OSMOverpassAdapter",
    "OSMPBFAdapter",
    "OfficialWebAdapter",
    "OpenAIDiscoveryAdapter",
    "OpenDataAdapter",
    "SourceAdapter",
    "TouringMediaAdapter",
]
