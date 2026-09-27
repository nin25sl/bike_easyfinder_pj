import pytest

from collection_worker.errors import ConfigurationError, PolicyError
from collection_worker.utils import canonicalize_url, normalize_name, redact_url_queries, validate_local_government_code


def test_region_codes_accept_prefecture_and_municipality():
    assert validate_local_government_code("40") == "40"
    assert validate_local_government_code("40130") == "40130"


def test_invalid_region_code_is_rejected():
    with pytest.raises(ConfigurationError):
        validate_local_government_code("Fukuoka")


def test_url_canonicalization_removes_tracking_and_fragment():
    assert canonicalize_url("HTTPS://Example.COM//spot?utm_source=x&a=1#top") == "https://example.com/spot?a=1"


def test_unsafe_url_scheme_is_rejected():
    with pytest.raises(PolicyError):
        canonicalize_url("file:///etc/passwd")


def test_url_credentials_are_rejected_and_query_is_redacted():
    with pytest.raises(PolicyError):
        canonicalize_url("https://user:secret@example.com/")
    assert redact_url_queries("failed https://example.com/a?token=secret") == "failed https://example.com/a?[REDACTED]"


def test_name_normalization():
    assert normalize_name(" 海の中道 （公園） ") == "海の中道"
