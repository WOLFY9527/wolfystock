# -*- coding: utf-8 -*-
"""Provider primitives for normalized provider result and error handling."""

from src.providers.errors import (
    ProviderCircuitOpen,
    ProviderError,
    ProviderForbidden,
    ProviderInvalidPayload,
    ProviderMissingCredentials,
    ProviderNoData,
    ProviderRateLimited,
    ProviderRetryDisposition,
    ProviderTimeout,
    ProviderUnauthorized,
    ProviderUnsupported,
    classify_provider_retry_disposition,
    normalize_provider_exception,
    provider_failed_result_from_exception,
    reason_from_http_status,
)
from src.providers.types import (
    ProviderCapability,
    ProviderReason,
    ProviderResult,
    ProviderSourceType,
    ProviderStatus,
)

__all__ = [
    "ProviderCapability",
    "ProviderCircuitOpen",
    "ProviderError",
    "ProviderForbidden",
    "ProviderInvalidPayload",
    "ProviderMissingCredentials",
    "ProviderNoData",
    "ProviderRateLimited",
    "ProviderRetryDisposition",
    "ProviderReason",
    "ProviderResult",
    "ProviderSourceType",
    "ProviderStatus",
    "ProviderTimeout",
    "ProviderUnauthorized",
    "ProviderUnsupported",
    "classify_provider_retry_disposition",
    "normalize_provider_exception",
    "provider_failed_result_from_exception",
    "reason_from_http_status",
]
