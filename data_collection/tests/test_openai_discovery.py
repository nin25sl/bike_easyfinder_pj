from types import SimpleNamespace

from collection_worker.adapters.openai_discovery import extract_citations


def test_citations_are_required_and_deduplicated():
    annotation = {"type": "url_citation", "url": "https://example.com/a?utm_source=x", "title": "A"}
    response = SimpleNamespace(output=[{
        "type": "message",
        "content": [{"annotations": [annotation, annotation, {"type": "other"}]}],
    }])
    assert extract_citations(response) == [{"url": "https://example.com/a", "title": "A"}]


def test_generated_text_without_url_is_discarded():
    response = SimpleNamespace(output=[{"type": "message", "content": [{"text": "candidate", "annotations": []}]}])
    assert extract_citations(response) == []
