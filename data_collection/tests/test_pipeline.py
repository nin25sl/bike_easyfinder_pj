from pathlib import Path

import pytest

from collection_worker.config import load_settings
from collection_worker.contracts import Region
from collection_worker.errors import ConfigurationError, PolicyError
from collection_worker.pipeline import dry_run_summary, validate_sources


@pytest.fixture
def settings(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    return load_settings(Path("data_collection/config/sources.yaml"))


def test_unknown_source_is_rejected(settings):
    with pytest.raises(ConfigurationError, match="Unknown sources"):
        validate_sources(settings, ["not_configured"])


def test_unapproved_source_is_rejected(settings):
    source_key = "openai_web_discovery"
    settings.sources[source_key] = settings.sources[source_key].model_copy(
        update={"approval_status": "pending"}
    )

    with pytest.raises(PolicyError, match="Sources are not approved"):
        validate_sources(settings, [source_key])


def test_openai_discovery_requires_api_key(settings):
    with pytest.raises(PolicyError, match="OPENAI_API_KEY"):
        validate_sources(settings, ["openai_web_discovery"])


def test_dry_run_summary_contains_no_secret_and_exposes_budget(settings):
    source_key = next(
        key for key, source in settings.sources.items() if source.approval_status == "approved"
    )
    region = Region(
        id="region-1",
        region_code="40",
        region_kind="prefecture",
        name_ja="福岡県",
        prefecture_code="40",
        parent_region_code=None,
        dataset_version="test",
        bbox=(129.9, 32.9, 131.2, 34.3),
    )

    summary = dry_run_summary(region, settings, [source_key], limit=25)

    assert summary["region_code"] == "40"
    assert summary["limit"] == 25
    assert summary["openai_budget"]["store"] is False
    assert "openai_api_key" not in str(summary).lower()
