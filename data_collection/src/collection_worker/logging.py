from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlsplit, urlunsplit


SENSITIVE_KEYS = {"authorization", "cookie", "set-cookie", "api_key", "openai_api_key"}


def sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key.lower() in SENSITIVE_KEYS else sanitize(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [sanitize(item) for item in value]
    return value


def safe_url(url: str | None) -> str | None:
    if not url:
        return url
    parts = urlsplit(url)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))


def emit(event_name: str, severity: str = "INFO", **fields: Any) -> None:
    payload = {
        "timestamp": datetime.now(UTC).isoformat(),
        "severity": severity,
        "event_name": event_name,
        **sanitize(fields),
    }
    logging.getLogger("collection_worker").log(
        getattr(logging, severity.upper(), logging.INFO),
        json.dumps(payload, ensure_ascii=False, default=str),
    )


def configure_logging(verbose: bool = False) -> None:
    logging.basicConfig(level=logging.DEBUG if verbose else logging.INFO, format="%(message)s")

