from __future__ import annotations

from typing import Any

from collection_worker.contracts import (
    NormalizedCandidate,
    ObservationInput,
    SpotObservation,
)

FIELD_DEFAULTS = {
    "business_status": "unknown",
    "parking": "unknown",
    "motorcycle_access": "unknown",
    "road_access": "unknown",
}


def normalize_payload(payload: dict[str, Any], method: str = "source_native") -> NormalizedCandidate:
    name = _string_or_none(payload.get("name") or payload.get("discovery_title"))
    address = _string_or_none(payload.get("address"))
    latitude = _float_or_none(payload.get("latitude"))
    longitude = _float_or_none(payload.get("longitude"))
    source_categories = _string_list(payload.get("source_categories"))
    features = _string_list(payload.get("features"))
    observations: list[ObservationInput] = []
    values = {
        "name": name,
        "address": address,
        "location": {"latitude": latitude, "longitude": longitude} if latitude is not None and longitude is not None else None,
        "source_categories": source_categories,
        "features": features,
        "opening_hours_text": _string_or_none(payload.get("opening_hours_text")),
        "business_status": _enum_value(payload.get("business_status"), {"open", "temporarily_closed", "permanently_closed", "unknown"}),
        "parking": _parking_value(payload.get("parking")),
        "motorcycle_access": _enum_value(payload.get("motorcycle_access"), {"allowed", "not_allowed", "unknown"}),
        "road_access": _enum_value(payload.get("road_access"), {"accessible", "restricted", "unknown"}),
        "suggested_stay_minutes": _int_or_none(payload.get("suggested_stay_minutes")),
        "official_url": _string_or_none(payload.get("official_url")),
        "touring_relevance": _float_or_none(payload.get("touring_relevance")),
        "touring_reasons": _string_list(payload.get("touring_reasons")),
        "source_payload": payload.get("_source_payload") or payload.get("osm_tags"),
    }
    for field_name, value in values.items():
        if value is None or value == []:
            continue
        observations.append(
            ObservationInput(
                field_name=field_name,
                value=value,
                raw_label=None,
                extraction_method=method,
                confidence=0.9 if method in {"source_native", "manual"} else 0.7,
            )
        )
    attribute_keys = {
        *FIELD_DEFAULTS.keys(), "opening_hours_text", "suggested_stay_minutes", "official_url",
        "touring_relevance", "touring_reasons",
    }
    attributes = {key: values[key] for key in attribute_keys}
    return NormalizedCandidate(
        name=name,
        address=address,
        latitude=latitude,
        longitude=longitude,
        source_categories=source_categories,
        features=features,
        attributes=attributes,
        observations=observations,
    )


def normalized_from_ai(spot: SpotObservation) -> NormalizedCandidate:
    payload = spot.model_dump()
    candidate = normalize_payload(payload, method="openai")
    evidence = {item.field: item.excerpt for item in spot.evidence}
    candidate.observations = [
        observation.model_copy(update={"evidence_excerpt": evidence.get(observation.field_name)})
        for observation in candidate.observations
    ]
    return candidate


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _float_or_none(value: Any) -> float | None:
    if value in {None, ""}:
        return None
    return float(value)


def _int_or_none(value: Any) -> int | None:
    if value in {None, ""}:
        return None
    return int(value)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    return [str(item).strip() for item in value if str(item).strip()]


def _enum_value(value: Any, allowed: set[str]) -> str:
    normalized = str(value or "unknown").strip().lower()
    return normalized if normalized in allowed else "unknown"


def _parking_value(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"available", "unavailable", "unknown"}:
        return normalized
    if not normalized:
        return "unknown"
    if any(token in normalized for token in ("なし", "無し", "無", "no parking")):
        return "unavailable"
    return "available"
