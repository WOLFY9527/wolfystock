"""Transport failure mapping into the normalized provider result."""

from __future__ import annotations

from typing import TypeVar

from src.contracts.evidence import SourceObservationFacts
from src.providers.errors import normalize_provider_exception
from src.providers.types import (
    ProviderCacheIdentity,
    ProviderCapability,
    ProviderDataResult,
)


_DataT = TypeVar("_DataT")


def provider_error_result_from_exception(
    exc: BaseException,
    *,
    capability: ProviderCapability,
    facts: SourceObservationFacts,
    cache_identity: ProviderCacheIdentity | None = None,
) -> ProviderDataResult[_DataT]:
    """Classify a real transport failure without treating empty data as failure."""

    return ProviderDataResult.error(
        capability,
        facts,
        reason=normalize_provider_exception(exc),
        error_message=str(exc) or exc.__class__.__name__,
        cache_identity=cache_identity,
    )


__all__ = ["provider_error_result_from_exception"]
