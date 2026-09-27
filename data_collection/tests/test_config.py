from pathlib import Path

import pytest

from collection_worker.config import load_settings
from collection_worker.errors import ConfigurationError


def test_checked_in_config_is_valid(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    settings = load_settings(Path("data_collection/config/sources.yaml"))
    assert settings.openai.store is False
    assert settings.openai.discovery_model == "gpt-6-astra"


def test_store_true_is_rejected(tmp_path):
    config = Path("data_collection/config/sources.yaml").read_text(encoding="utf-8")
    path = tmp_path / "sources.yaml"
    path.write_text(config.replace("store: false", "store: true"), encoding="utf-8")
    with pytest.raises(ConfigurationError):
        load_settings(path)
