from __future__ import annotations

import random
import time
from dataclasses import dataclass
from email.utils import parsedate_to_datetime
from typing import Mapping
from urllib.parse import urlsplit

import httpx

from collection_worker.errors import PermanentSourceError, TemporarySourceError
from collection_worker.utils import assert_public_http_url


@dataclass
class FetchResult:
    url: str
    status_code: int
    content: bytes
    headers: dict[str, str]


def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
    if response is not None and response.headers.get("Retry-After"):
        raw = response.headers["Retry-After"]
        try:
            return min(float(raw), 300)
        except ValueError:
            try:
                return max(0, min((parsedate_to_datetime(raw).timestamp() - time.time()), 300))
            except Exception:
                pass
    return min(2**attempt, 60) + random.random()


def fetch_url(
    url: str,
    *,
    allowed_domain: str | None,
    timeout_seconds: int,
    max_bytes: int,
    headers: Mapping[str, str] | None = None,
    max_retries: int = 3,
) -> FetchResult:
    current = assert_public_http_url(url, allowed_domain)
    request_headers = {"Accept": "application/json,text/csv,text/html;q=0.9,*/*;q=0.5", **(headers or {})}
    with httpx.Client(timeout=timeout_seconds, follow_redirects=False, headers=request_headers) as client:
        for attempt in range(max_retries + 1):
            response = None
            try:
                response = client.get(current)
                if response.is_redirect:
                    location = response.headers.get("Location")
                    if not location:
                        raise PermanentSourceError("Redirect has no Location header")
                    current = str(response.url.join(location))
                    current = assert_public_http_url(current, allowed_domain)
                    continue
                if response.status_code in {408, 429} or response.status_code >= 500:
                    if attempt >= max_retries:
                        raise TemporarySourceError(f"HTTP {response.status_code}: {current}")
                    time.sleep(_retry_delay(response, attempt + 1))
                    continue
                if response.status_code >= 400:
                    raise PermanentSourceError(f"HTTP {response.status_code}: {current}")
                content = response.content
                if len(content) > max_bytes:
                    raise PermanentSourceError(f"Response exceeds {max_bytes} bytes")
                safe_headers = {
                    key: value
                    for key, value in response.headers.items()
                    if key.lower() not in {"set-cookie", "authorization", "proxy-authorization"}
                }
                return FetchResult(str(response.url), response.status_code, content, safe_headers)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                if attempt >= max_retries:
                    raise TemporarySourceError(f"Network error: {url}") from exc
                time.sleep(_retry_delay(response, attempt + 1))
    raise TemporarySourceError(f"Fetch did not complete: {url}")


def domain_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()

