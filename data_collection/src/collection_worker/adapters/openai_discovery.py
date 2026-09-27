from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from openai import OpenAI

from collection_worker.adapters.base import SourceAdapter
from collection_worker.contracts import DiscoveredRecord, Region
from collection_worker.errors import PolicyError, TemporarySourceError
from collection_worker.utils import canonicalize_url, stable_hash


def _dump(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if hasattr(value, "model_dump"):
        return value.model_dump()
    return {}


def extract_citations(response: Any) -> list[dict[str, str]]:
    citations: dict[str, str] = {}
    for output in getattr(response, "output", []) or []:
        item = _dump(output)
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            for annotation in content.get("annotations", []):
                if annotation.get("type") != "url_citation" or not annotation.get("url"):
                    continue
                url = canonicalize_url(annotation["url"])
                citations[url] = annotation.get("title") or url
    return [{"url": url, "title": title} for url, title in citations.items()]


class OpenAIDiscoveryAdapter(SourceAdapter):
    last_metadata: dict[str, Any] | None = None

    def discover(self, region: Region, limit: int | None = None) -> Iterable[DiscoveredRecord]:
        if not self.settings.openai_api_key:
            raise PolicyError("OPENAI_API_KEY is required for openai_web_discovery")
        client = OpenAI(
            api_key=self.settings.openai_api_key,
            timeout=self.settings.openai.request_timeout_seconds,
            max_retries=self.settings.openai.max_retries,
        )
        themes = list(self.source.config.get("search_themes", []))
        prompt = (
            f"日本の{region.name_ja}（行政区域コード {region.region_code}）にある、"
            "日帰りバイクツーリングの目的地候補を調査してください。"
            f"観点: {', '.join(themes)}。候補ごとに根拠となる公開ページを引用してください。"
            "同じ場所の重複、まとめサイトだけを根拠にした候補、地域外の候補を避けてください。"
        )
        try:
            response = client.responses.create(
                model=self.settings.openai.discovery_model,
                tools=[{"type": "web_search"}],
                input=prompt,
                store=False,
            )
        except Exception as exc:
            raise TemporarySourceError(f"OpenAI source discovery failed: {type(exc).__name__}") from exc
        citations = extract_citations(response)
        usage = getattr(response, "usage", None)
        raw_status = getattr(response, "status", "completed")
        self.last_metadata = {
            "response_id": getattr(response, "id", None),
            "model": getattr(response, "model", self.settings.openai.discovery_model),
            "status": str(getattr(raw_status, "value", raw_status)),
            "input_hash": stable_hash(prompt),
            "input_tokens": getattr(usage, "input_tokens", None),
            "output_tokens": getattr(usage, "output_tokens", None),
            "web_search_calls": sum(
                1 for item in (getattr(response, "output", []) or [])
                if _dump(item).get("type") == "web_search_call"
            ),
        }
        selected = citations if limit is None else citations[:limit]
        for citation in selected:
            yield DiscoveredRecord(
                source_record_id=stable_hash(citation["url"]),
                source_url=citation["url"],
                payload={
                    "discovery_title": citation["title"],
                    "openai_response_id": getattr(response, "id", None),
                    "openai_model": getattr(response, "model", self.settings.openai.discovery_model),
                },
                content_type="application/x.openai-citation",
                title=citation["title"],
            )
