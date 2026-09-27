import importlib.util
import sys
from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "apple_maps_poc.py"
SPEC = importlib.util.spec_from_file_location("apple_maps_poc", SCRIPT)
assert SPEC and SPEC.loader
poc = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = poc
SPEC.loader.exec_module(poc)


def test_generated_template_has_required_coverage(tmp_path):
    path = tmp_path / "routes.csv"
    poc.generate_template(path)
    cases = poc.load_cases(path)

    assert len(cases) == 140
    assert set(case.prefecture for case in cases) == set(poc.PREFECTURES)
    assert sum(not case.highway_allowed for case in cases) == 28


def test_summary_stays_pending_without_manual_gates():
    cases = [
        poc.RouteCase("fukuoka-01", "fukuoka", "urban", 33, 130, 33.1, 130.1, True, 100)
    ]
    results = [
        poc.Measurement("fukuoka-01", "fukuoka", "urban", True, 200, 20, 100, 1000, None, 100, 0, None)
    ]

    summary = poc.summarize(cases, results)

    assert summary["decision"] == "PENDING_OR_FAIL"
    assert summary["gates"]["manual_highway_and_asymmetry_review"] is False
