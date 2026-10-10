from __future__ import annotations

from typing import Any

from collection_worker.contracts import DiscoveredRecord

OSM_TAG_FILTERS: dict[str, set[str] | None] = {
    "tourism": None,
    "amenity": {"cafe", "restaurant", "public_bath", "parking"},
    "leisure": {"park", "nature_reserve"},
    "natural": {"peak", "beach", "hot_spring", "cliff"},
    "historic": None,
    "place": {"locality"},
}


def relevant_tags(tags: dict[str, str]) -> bool:
    if not (tags.get("name") or tags.get("name:ja")):
        return False
    if tags.get("information") in {"guidepost", "board", "map"} and len(tags) <= 2:
        return False
    return any(key in tags and (allowed is None or tags[key] in allowed) for key, allowed in OSM_TAG_FILTERS.items())


def osm_record(
    kind: str,
    osm_id: int | str,
    tags: dict[str, str],
    latitude: float | None,
    longitude: float | None,
    *,
    raw_text: str,
    response_headers: dict[str, str] | None = None,
    http_status: int | None = None,
    extra_payload: dict[str, Any] | None = None,
) -> DiscoveredRecord:
    record_id = f"{kind}/{osm_id}"
    return DiscoveredRecord(
        source_record_id=record_id,
        source_url=f"https://www.openstreetmap.org/{kind}/{osm_id}",
        payload={
            "source_record_id": record_id,
            "name": tags.get("name") or tags.get("name:ja"),
            "address": tags.get("addr:full") or _joined_address(tags),
            "latitude": latitude,
            "longitude": longitude,
            "opening_hours_text": tags.get("opening_hours"),
            "parking": "available" if tags.get("parking") or tags.get("amenity") == "parking" else "unknown",
            "motorcycle_access": "allowed" if tags.get("motorcycle") in {"yes", "designated"} else "unknown",
            "official_url": tags.get("contact:website") or tags.get("website"),
            "source_categories": [
                f"{key}={value}" for key, value in tags.items() if key in OSM_TAG_FILTERS
            ],
            "features": [],
            "osm_tags": tags,
            "_source_payload": {"osm_tags": tags, **(extra_payload or {})},
            **(extra_payload or {}),
        },
        raw_text=raw_text,
        content_type="application/json",
        response_headers=response_headers or {},
        http_status=http_status,
        title=tags.get("name"),
    )


def _joined_address(tags: dict[str, str]) -> str | None:
    values = [tags.get(key) for key in ("addr:province", "addr:city", "addr:suburb", "addr:street", "addr:housenumber")]
    joined = "".join(value for value in values if value)
    return joined or None
