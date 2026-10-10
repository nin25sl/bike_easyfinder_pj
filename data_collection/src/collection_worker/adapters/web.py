from __future__ import annotations

import time
from collections.abc import Iterable
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit
from urllib.robotparser import RobotFileParser

from collection_worker.adapters.base import SourceAdapter
from collection_worker.contracts import DiscoveredRecord, Region
from collection_worker.errors import PermanentSourceError, PolicyError
from collection_worker.http import domain_of, fetch_url
from collection_worker.utils import stable_hash


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []
        self.ignored = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style", "noscript", "svg"}:
            self.ignored += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "noscript", "svg"} and self.ignored:
            self.ignored -= 1

    def handle_data(self, data: str) -> None:
        if not self.ignored and data.strip():
            self.parts.append(data.strip())

    def text(self) -> str:
        return "\n".join(self.parts)


class ApprovedWebAdapter(SourceAdapter):
    discovery_signal = False

    def discover(self, region: Region, limit: int | None = None) -> Iterable[DiscoveredRecord]:
        pages = list(self.source.config.get("pages", []))
        emitted = 0
        last_request = 0.0
        minimum_interval = 60.0 / self.source.rate_limit_per_minute
        for page in pages[: self.source.max_pages_per_run]:
            url = str(page["url"] if isinstance(page, dict) else page)
            allowed_regions = [str(item) for item in (page.get("region_codes", []) if isinstance(page, dict) else [])]
            if allowed_regions and region.region_code not in allowed_regions and region.prefecture_code not in allowed_regions:
                continue
            crawl_delay = self._enforce_robots(url)
            effective_interval = max(minimum_interval, crawl_delay or 0.0)
            delay = effective_interval - (time.monotonic() - last_request)
            if delay > 0:
                time.sleep(delay)
            result = fetch_url(
                url,
                allowed_domain=domain_of(url),
                timeout_seconds=self.source.request_timeout_seconds,
                max_bytes=self.settings.collection.max_response_bytes,
                headers={"User-Agent": str(self.source.config.get("user_agent", "BikeEasyFinder/0.1"))},
                max_retries=self.settings.openai.max_retries,
            )
            last_request = time.monotonic()
            content_type = result.headers.get("content-type", "text/html")
            if "html" not in content_type.lower():
                raise PermanentSourceError(f"Expected HTML from {url}; received {content_type}")
            lowered = result.content[:250_000].lower()
            if b"captcha" in lowered or b"recaptcha" in lowered or "/login" in urlsplit(result.url).path.lower():
                raise PolicyError(f"Interactive access gate detected; collection stopped: {url}")
            parser = _TextExtractor()
            parser.feed(result.content.decode(str(self.source.config.get("encoding", "utf-8")), errors="replace"))
            text = parser.text()
            if not text:
                raise PermanentSourceError(f"No readable page text: {url}")
            title = page.get("title") if isinstance(page, dict) else None
            payload = {
                "name": title,
                "_ai_extract": bool(self.source.config.get("ai_extract", True)),
                "_touring_signal": self.discovery_signal,
                "source_page_url": result.url,
            }
            yield DiscoveredRecord(
                source_record_id=str(page.get("source_record_id") if isinstance(page, dict) and page.get("source_record_id") else stable_hash(result.url)),
                source_url=result.url,
                payload=payload,
                raw_text=text,
                content_type=content_type,
                response_headers=result.headers,
                http_status=result.status_code,
                title=title,
            )
            emitted += 1
            if limit is not None and emitted >= limit:
                return

    def _enforce_robots(self, url: str) -> float | None:
        if not self.source.config.get("robots_required", True):
            return None
        split = urlsplit(url)
        robots_url = urljoin(f"{split.scheme}://{split.netloc}", "/robots.txt")
        try:
            result = fetch_url(
                robots_url,
                allowed_domain=split.hostname,
                timeout_seconds=self.source.request_timeout_seconds,
                max_bytes=512_000,
                headers={"User-Agent": str(self.source.config.get("user_agent", "BikeEasyFinder/0.1"))},
                max_retries=1,
            )
        except PermanentSourceError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise PolicyError(f"Could not verify robots policy for {url}") from exc
        parser = RobotFileParser()
        parser.set_url(robots_url)
        parser.parse(result.content.decode("utf-8", errors="replace").splitlines())
        user_agent = str(self.source.config.get("user_agent", "BikeEasyFinder"))
        if not parser.can_fetch(user_agent, url):
            raise PolicyError(f"robots.txt disallows collection: {url}")
        return parser.crawl_delay(user_agent) or parser.crawl_delay("*")


class OfficialWebAdapter(ApprovedWebAdapter):
    pass


class GeneralWebAdapter(ApprovedWebAdapter):
    pass


class TouringMediaAdapter(ApprovedWebAdapter):
    discovery_signal = True
