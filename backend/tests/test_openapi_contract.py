from pathlib import Path
import os

import yaml


def test_static_openapi_is_version_1_1_and_has_only_public_mvp_paths() -> None:
    path = Path(
        os.getenv(
            "OPENAPI_CONTRACT_PATH",
            Path(__file__).parents[2] / "docs" / "bike_easyfinder_pj" / "SystemDesign" / "mvp-openapi-v1.yaml",
        )
    )
    contract = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert contract["info"]["version"] == "1.1.0"
    assert set(contract["paths"]) == {
        "/recommendations",
        "/interactions",
        "/installations/{installation_id}/data",
    }
    response = contract["components"]["schemas"]["RecommendationResponse"]
    assert {"recommendation_rule_version", "data_version"}.issubset(response["required"])
