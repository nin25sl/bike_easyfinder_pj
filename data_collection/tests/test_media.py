from __future__ import annotations

import io

from PIL import Image

from collection_worker.config import load_settings
from collection_worker.media import accepted_license, distance_meters, parse_candidate, validate_and_transform


def test_license_allowlist_is_conservative():
    assert accepted_license("CC BY-SA 4.0") == "CC-BY-SA-4.0"
    assert accepted_license("CC0") == "CC0"
    assert accepted_license("Public domain") == "Public Domain"
    assert accepted_license("CC BY-NC 4.0") is None
    assert accepted_license("CC BY-ND 4.0") is None
    assert accepted_license("GFDL") is None
    assert accepted_license("") is None


def test_candidate_metadata_is_plain_and_complete():
    candidate = parse_candidate({
        "pageid": 123,
        "lastrevid": 456,
        "title": "File:福岡タワー.jpg",
        "imageinfo": [{
            "url": "https://upload.wikimedia.org/example.jpg",
            "descriptionurl": "https://commons.wikimedia.org/wiki/File:example.jpg",
            "mime": "image/jpeg", "width": 2000, "height": 1000,
            "extmetadata": {
                "Artist": {"value": "<b>Example Author</b>"},
                "LicenseShortName": {"value": "CC BY-SA 4.0"},
                "LicenseUrl": {"value": "https://creativecommons.org/licenses/by-sa/4.0/"},
                "GPSLatitude": {"value": "33.593"},
                "GPSLongitude": {"value": "130.351"},
            },
        }],
    })
    assert candidate.creator == "Example Author"
    assert candidate.license_name == "CC-BY-SA-4.0"
    assert candidate.latitude == 33.593


def test_image_validation_and_webp_resize():
    settings = load_settings("data_collection/config/sources.yaml")
    source = io.BytesIO()
    Image.new("RGB", (3200, 1200), "blue").save(source, "JPEG")
    derivative, mime, width, height = validate_and_transform(source.getvalue(), settings)
    assert mime == "image/jpeg"
    assert (width, height) == (3200, 1200)
    with Image.open(io.BytesIO(derivative)) as image:
        assert image.format == "WEBP"
        assert max(image.size) == 1600


def test_distance_meters():
    assert distance_meters(33.5902, 130.4017, 33.5902, 130.4017) == 0
    assert 800 < distance_meters(33.5902, 130.4017, 33.5992, 130.4017) < 1200
