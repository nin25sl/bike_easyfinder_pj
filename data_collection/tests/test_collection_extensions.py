import json
from pathlib import Path

from collection_worker.adapters.base import SourceAdapter
from collection_worker.adapters.manual import ManualSeedAdapter
from collection_worker.adapters.osm import OSMPBFAdapter, _PROCESS_EXTRACT_CACHE
from collection_worker.adapters.osm_common import osm_record, relevant_tags
from collection_worker.adapters.web import _TextExtractor
from collection_worker.config import load_settings
from collection_worker.contracts import DiscoveredRecord, Region
from collection_worker.pipeline import collect_all
from collection_worker.resolution import _decision, _field_score, _score


class ExampleAdapter(SourceAdapter):
    def discover(self, region: Region, limit: int | None = None):
        for index in range(5):
            yield DiscoveredRecord(
                source_record_id=str(index),
                source_url=f"https://example.com/{index}",
            )


def _region() -> Region:
    return Region(
        id="00000000-0000-0000-0000-000000000001",
        region_code="40",
        region_kind="prefecture",
        name_ja="福岡県",
        prefecture_code="40",
        parent_region_code=None,
        dataset_version="test",
        bbox=(129.9, 32.9, 131.2, 34.3),
    )


def test_adapter_pages_resume_from_checkpoint(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = load_settings(Path("data_collection/config/sources.yaml"))
    settings.collection.checkpoint_every = 2
    source = settings.sources["manual_seed"]
    adapter = ExampleAdapter("example", source, settings)

    pages = list(adapter.iter_pages(_region(), checkpoint={"offset": 2}))

    assert [[item.source_record_id for item in page.records] for page in pages] == [["2", "3"], ["4"]]
    assert pages[-1].checkpoint["offset"] == 5
    assert pages[-1].checkpoint["page"] == 2
    assert pages[-1].checkpoint["last_item"] == "4"
    assert pages[-1].checkpoint["updated_at"]
    assert pages[-1].complete is True


def test_manual_seed_prefecture_includes_municipality_records():
    assert ManualSeedAdapter._matches_region("40130", _region())
    assert not ManualSeedAdapter._matches_region("43100", _region())


def test_resolution_threshold_scoring_is_stable():
    score, evidence = _score({
        "name_similarity": 0.91,
        "distance_m": 45,
        "address_match": True,
        "url_match": False,
        "category_match": True,
    })
    assert score == 90
    assert evidence["distance_m"] == 45.0


def test_entity_resolution_golden_precision_and_review_recall():
    fixture = Path("data_collection/tests/fixtures/entity-resolution-golden.json")
    cases = json.loads(fixture.read_text(encoding="utf-8"))
    outcomes = []
    for case in cases:
        score, _ = _score(case)
        outcomes.append(_decision(score, case["same_source"], case["distance_m"]))
    predicted_merges = [index for index, outcome in enumerate(outcomes) if outcome == "merge"]
    true_merges = {index for index, case in enumerate(cases) if case["expected"] == "merge"}
    precision = sum(index in true_merges for index in predicted_merges) / len(predicted_merges)
    assert precision >= 0.98
    assert outcomes == [case["expected"] for case in cases]
    assert all(
        outcome == "review"
        for outcome, case in zip(outcomes, cases, strict=True)
        if case["expected"] == "review"
    )


def test_field_selection_prefers_verified_official_source():
    official = _field_score("opening_hours_text", "official_web", "verified", 0.8)
    osm = _field_score("opening_hours_text", "osm_pbf", "verified", 1.0)
    coordinate = _field_score("location", "osm_pbf", "verified", 0.9)
    assert official > osm
    assert coordinate > _field_score("location", "official_web", "verified", 0.9)


def test_osm_normalization_is_shared_by_pbf_and_overpass():
    tags = {"name": "展望台", "tourism": "viewpoint", "website": "https://example.com"}
    assert relevant_tags(tags)
    record = osm_record("node", 1, tags, 33.5, 130.4, raw_text="{}")
    assert record.source_record_id == "node/1"
    assert record.payload["official_url"] == "https://example.com"
    assert record.payload["source_categories"] == ["tourism=viewpoint"]


def test_unnamed_osm_features_are_not_candidates():
    assert not relevant_tags({"amenity": "parking"})
    record = osm_record(
        "node", 2, {"name:ja": "日本語名", "tourism": "viewpoint"}, 33.5, 130.4, raw_text="{}"
    )
    assert record.payload["name"] == "日本語名"


def test_html_text_extractor_excludes_script_and_style():
    parser = _TextExtractor()
    parser.feed("<html><style>hidden</style><body><h1>Spot</h1><script>bad()</script><p>Facts</p></body></html>")
    assert parser.text() == "Spot\nFacts"


def test_collect_all_dry_run_uses_profile_without_database(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = load_settings(Path("data_collection/config/sources.yaml"))
    result = collect_all(object(), settings, "fukuoka-pilot", "fukuoka", "initial", dry_run=True)
    assert result["regions"] == ["40"]
    assert result["sources"] == ["osm_pbf", "fukuoka_codex_reviewed"]


def test_osm_pbf_adapter_streams_and_filters_region(monkeypatch):
    from shapely.geometry import box

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = load_settings(Path("data_collection/config/sources.yaml"))
    source = settings.sources["osm_pbf"].model_copy(update={
        "config": {"extract_path": "data_collection/tests/fixtures/osm-mini.osm"}
    })
    region = _region().model_copy(update={
        "bbox": (130.0, 33.0, 131.0, 34.0),
        "geometry_wkb": box(130.0, 33.0, 131.0, 34.0).wkb,
    })

    records = list(OSMPBFAdapter("osm_pbf", source, settings).discover(region))

    assert len(records) == 4
    assert {item.source_record_id for item in records} == {"node/1", "way/10", "way/11", "relation/20"}
    assert all(item.source_record_id != "node/2" for item in records)
    node_raw = json.loads(next(item for item in records if item.source_record_id == "node/1").raw_text)
    assert node_raw["lat"] == 33.5
    assert node_raw["lon"] == 130.4
    area = next(item for item in records if item.source_record_id == "way/11")
    assert area.payload["geometry_missing"] is False
    assert area.payload["_source_payload"]["pbf_extract"]
    assert area.payload["latitude"] == 33.535
    assert area.payload["longitude"] == 130.435
    relation = next(item for item in records if item.source_record_id == "relation/20")
    assert relation.payload["geometry_missing"] is True


def test_osm_pbf_extract_is_pinned_for_process(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = load_settings(Path("data_collection/config/sources.yaml"))
    url = "https://example.invalid/kyushu-latest.osm.pbf"
    source = settings.sources["osm_pbf"].model_copy(update={
        "base_url": url,
        "config": {"extract_url": url},
    })
    snapshot = tmp_path / "kyushu-2026-10-05.osm.pbf"
    snapshot.write_bytes(b"snapshot")
    metadata = {"url": "https://example.invalid/kyushu-2026-10-05.osm.pbf", "sha256": "abc"}
    monkeypatch.setitem(_PROCESS_EXTRACT_CACHE, url, (snapshot, metadata))

    path, resolved_metadata = OSMPBFAdapter("osm_pbf", source, settings)._extract()

    assert path == snapshot
    assert resolved_metadata == metadata
