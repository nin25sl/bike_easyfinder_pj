from __future__ import annotations

import hashlib
import ipaddress
import re
import socket
import unicodedata
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from rapidfuzz.fuzz import ratio

from collection_worker.errors import ConfigurationError, PolicyError


TRACKING_PARAMETERS = {"fbclid", "gclid", "mc_cid", "mc_eid", "ref", "source"}


def validate_local_government_code(value: str) -> str:
    digits = re.sub(r"\D", "", value)
    if len(digits) in {2, 5}:
        return digits
    if len(digits) == 6:
        base, supplied = digits[:5], int(digits[5])
        remainder = sum(int(n) * weight for n, weight in zip(base, (6, 5, 4, 3, 2), strict=True)) % 11
        expected = 11 - remainder
        if expected >= 10:
            expected = 0
        if supplied != expected:
            raise ConfigurationError(f"Invalid local government check digit: {value}")
        return base
    raise ConfigurationError("Region code must be 2, 5, or validated 6 digits")


def canonicalize_url(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise PolicyError(f"Unsupported URL: {url}")
    if parts.username or parts.password:
        raise PolicyError("Credentials in URLs are not allowed")
    host = parts.hostname.lower().rstrip(".")
    port = parts.port
    if port and port not in {80, 443}:
        raise PolicyError(f"Unsupported URL port: {port}")
    netloc = host if not port else f"{host}:{port}"
    params = []
    for key, value in parse_qsl(parts.query, keep_blank_values=True):
        if key.lower().startswith("utm_") or key.lower() in TRACKING_PARAMETERS:
            continue
        params.append((key, value))
    path = re.sub(r"/{2,}", "/", parts.path or "/")
    return urlunsplit((parts.scheme.lower(), netloc, path, urlencode(params), ""))


def assert_public_http_url(url: str, allowed_domain: str | None = None) -> str:
    canonical = canonicalize_url(url)
    host = urlsplit(canonical).hostname
    assert host is not None
    if allowed_domain and host != allowed_domain and not host.endswith(f".{allowed_domain}"):
        raise PolicyError(f"Redirect/domain is not allowed: {host}")
    try:
        addresses = {info[4][0] for info in socket.getaddrinfo(host, None)}
    except socket.gaierror as exc:
        raise PolicyError(f"Could not resolve URL host: {host}") from exc
    for raw in addresses:
        if not ipaddress.ip_address(raw.split("%")[0]).is_global:
            raise PolicyError(f"Non-public destination rejected: {host}")
    return canonical


def normalize_name(value: str | None) -> str | None:
    if not value:
        return None
    normalized = unicodedata.normalize("NFKC", value)
    normalized = re.sub(r"[\(（].*?[\)）]", "", normalized)
    normalized = re.sub(r"[\s・･·]+", "", normalized)
    return normalized.casefold().strip() or None


def name_similarity(left: str | None, right: str | None) -> float:
    left_n, right_n = normalize_name(left), normalize_name(right)
    if not left_n or not right_n:
        return 0.0
    return ratio(left_n, right_n) / 100


def stable_hash(*values: str) -> str:
    return hashlib.sha256("\x1f".join(values).encode("utf-8")).hexdigest()


def redact_url_queries(value: str) -> str:
    return re.sub(r"(https?://[^\s?]+)\?[^\s]+", r"\1?[REDACTED]", value)
