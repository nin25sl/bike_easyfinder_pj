from collection_worker.normalize import normalize_payload


def test_native_payload_becomes_candidate_with_provenance_fields():
    result = normalize_payload(
        {
            "name": "Spot A",
            "address": "Fukuoka",
            "latitude": 33.5,
            "longitude": 130.4,
            "source_categories": ["tourism=attraction"],
        }
    )
    assert result.name == "Spot A"
    assert result.latitude == 33.5
    names = {item.field_name for item in result.observations}
    assert {"name", "address", "location", "source_categories"} <= names
    assert all(item.extraction_method == "source_native" for item in result.observations)
