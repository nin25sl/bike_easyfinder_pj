class CollectionError(Exception):
    """Base exception carrying a stable operator-facing error code."""

    code = "COLLECTION_ERROR"
    exit_code = 5


class ConfigurationError(CollectionError):
    code = "CONFIGURATION_ERROR"
    exit_code = 3


class PolicyError(CollectionError):
    code = "POLICY_ERROR"
    exit_code = 4


class TemporarySourceError(CollectionError):
    code = "TEMPORARY_SOURCE_ERROR"
    exit_code = 2


class PermanentSourceError(CollectionError):
    code = "PERMANENT_SOURCE_ERROR"
    exit_code = 2


class UnsupportedSourceError(CollectionError):
    code = "SOURCE_NOT_IMPLEMENTED"
    exit_code = 4

