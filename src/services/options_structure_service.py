# -*- coding: utf-8 -*-
"""Provider-neutral options structure contract and safe aggregation helpers."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
import re
from typing import Iterable, Literal, Protocol, Sequence

from api.v1.schemas.options import (
    OptionChainSnapshot,
    OptionContractStructureRow,
    OptionsExpirationExposureSummary,
    OptionsGammaFlipLevel,
    OptionsNearestExpirationBucket,
    OptionsStrikeExposureSummary,
    OptionsStructureSummary,
    OptionsZeroDteConcentration,
)


OPTIONS_STRUCTURE_PROVIDER_MISSING_REASON = "options_structure_provider_missing"
OPTIONS_STRUCTURE_PROVIDER_STATE_MISSING = "provider_missing"
OPTIONS_STRUCTURE_PROVIDER_STATE_ENTITLEMENT_REQUIRED = "entitlement_required"
OPTIONS_STRUCTURE_PROVIDER_STATE_UNAVAILABLE = "provider_unavailable"
_CONTRACT_MULTIPLIER_FALLBACK = 100
_SAFE_PROVIDER_UNAVAILABLE_REASONS = {
    OPTIONS_STRUCTURE_PROVIDER_STATE_MISSING,
    OPTIONS_STRUCTURE_PROVIDER_STATE_ENTITLEMENT_REQUIRED,
    OPTIONS_STRUCTURE_PROVIDER_STATE_UNAVAILABLE,
    "unsupported_symbol",
}
_FORBIDDEN_PUBLIC_REASON_MARKERS = (
    "apikey",
    "api_key",
    "cachekey",
    "cache_key",
    "credential",
    "env",
    "exceptionchain",
    "exception_chain",
    "exceptionclass",
    "exception_class",
    "providerclass",
    "provider_class",
    "providername",
    "provider_name",
    "rawpayload",
    "raw_payload",
    "requestid",
    "request_id",
    "token",
    "traceid",
    "trace_id",
)


OptionsStructureUnavailableReason = Literal[
    "provider_missing",
    "entitlement_required",
    "provider_unavailable",
    "unsupported_symbol",
]


@dataclass(frozen=True, slots=True)
class OptionsStructureProviderRequest:
    """Provider-neutral request passed to future options chain providers."""

    symbol: str
    as_of: str | None = None
    expiration_filters: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True, slots=True)
class OptionsStructureProviderUnavailableResult:
    """Structured provider result that keeps unavailable states consumer-safe."""

    reason_code: OptionsStructureUnavailableReason = OPTIONS_STRUCTURE_PROVIDER_STATE_UNAVAILABLE
    blocking_reasons: tuple[str, ...] = field(default_factory=tuple)


OptionsStructureProviderResult = OptionChainSnapshot | OptionsStructureProviderUnavailableResult


class OptionsStructureProvider(Protocol):
    """Interface future options chain providers implement behind the gateway."""

    def fetch_options_structure(
        self,
        request: OptionsStructureProviderRequest,
    ) -> OptionsStructureProviderResult:
        """Return a normalized option-chain snapshot or a structured unavailable result."""


def _dedupe_codes(values: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        ordered.append(text)
    return ordered


def _consumer_safe_reason_codes(values: Iterable[str]) -> list[str]:
    safe: list[str] = []
    for value in _dedupe_codes(values):
        text = re.sub(r"[^A-Za-z0-9_.:-]+", "_", value).strip("_")
        lowered = text.lower()
        if not text or len(text) > 80:
            continue
        if any(marker in lowered for marker in _FORBIDDEN_PUBLIC_REASON_MARKERS):
            continue
        safe.append(text)
    return _dedupe_codes(safe)


def _normalize_symbol(symbol: str) -> str:
    normalized = re.sub(r"\s+", "", str(symbol or "")).upper()
    return normalized or "UNKNOWN"


def _parse_date(value: str | None) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text[:10])
    except ValueError:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError:
            return None


def _dte(expiration: str | None, as_of: str | None) -> int | None:
    expiration_date = _parse_date(expiration)
    snapshot_date = _parse_date(as_of)
    if expiration_date is None or snapshot_date is None:
        return None
    return max(0, (expiration_date - snapshot_date).days)


def _safe_sum(values: Iterable[int | None]) -> int:
    return sum(int(value) for value in values if value is not None)


def _round_optional(value: float | None) -> float | None:
    return round(value, 2) if value is not None else None


def _dte_sort_value(expiration: str | None, as_of: str | None) -> int:
    value = _dte(expiration, as_of)
    return value if value is not None else 99999


def _contract_gamma_exposure(
    contract: OptionContractStructureRow,
    *,
    spot_price: float | None,
) -> tuple[float | None, list[str]]:
    missing: list[str] = []
    if spot_price is None:
        missing.append("missing_spot_price")
    if contract.gamma is None:
        missing.append("missing_gamma")
    if contract.open_interest is None:
        missing.append("missing_open_interest")
    multiplier = contract.multiplier if contract.multiplier is not None else _CONTRACT_MULTIPLIER_FALLBACK
    if multiplier <= 0:
        missing.append("missing_multiplier")
    if missing:
        return None, missing

    sign = 1.0 if contract.side == "call" else -1.0
    value = (
        sign
        * float(contract.gamma)
        * int(contract.open_interest)
        * int(multiplier)
        * float(spot_price)
        * float(spot_price)
        * 0.01
    )
    return round(value, 2), []


def _combine_exposures(values: Iterable[float | None]) -> float | None:
    present = [float(value) for value in values if value is not None]
    if not present:
        return None
    return round(sum(present), 2)


def _calculation_state(contract_count: int, exposure_count: int) -> str:
    if contract_count <= 0 or exposure_count <= 0:
        return "not_available"
    if exposure_count < contract_count:
        return "degraded"
    return "available"


def _summarize_strikes(snapshot: OptionChainSnapshot) -> tuple[list[OptionsStrikeExposureSummary], list[str]]:
    groups: dict[float, list[OptionContractStructureRow]] = defaultdict(list)
    for contract in snapshot.contracts:
        groups[float(contract.strike)].append(contract)

    summaries: list[OptionsStrikeExposureSummary] = []
    missing_inputs: list[str] = []
    for strike, contracts in sorted(groups.items()):
        group_missing_inputs: list[str] = []
        call_contracts = [contract for contract in contracts if contract.side == "call"]
        put_contracts = [contract for contract in contracts if contract.side == "put"]
        call_exposures: list[float | None] = []
        put_exposures: list[float | None] = []
        for contract in contracts:
            exposure, missing = _contract_gamma_exposure(contract, spot_price=snapshot.spot_price)
            missing_inputs.extend(missing)
            group_missing_inputs.extend(missing)
            if contract.side == "call":
                call_exposures.append(exposure)
            else:
                put_exposures.append(exposure)
        exposure_count = sum(1 for value in [*call_exposures, *put_exposures] if value is not None)
        expirations = {contract.expiration for contract in contracts if contract.expiration}
        summaries.append(
            OptionsStrikeExposureSummary(
                strike=strike,
                expiration=next(iter(expirations)) if len(expirations) == 1 else None,
                contractCount=len(contracts),
                callOpenInterest=_safe_sum(contract.open_interest for contract in call_contracts),
                putOpenInterest=_safe_sum(contract.open_interest for contract in put_contracts),
                callVolume=_safe_sum(contract.volume for contract in call_contracts),
                putVolume=_safe_sum(contract.volume for contract in put_contracts),
                callDealerGammaExposure=_round_optional(_combine_exposures(call_exposures)),
                putDealerGammaExposure=_round_optional(_combine_exposures(put_exposures)),
                netDealerGammaExposure=_round_optional(_combine_exposures([*call_exposures, *put_exposures])),
                calculationState=_calculation_state(len(contracts), exposure_count),
                missingInputs=_dedupe_codes(group_missing_inputs),
            )
        )
    return summaries, _dedupe_codes(missing_inputs)


def _summarize_expirations(snapshot: OptionChainSnapshot) -> tuple[list[OptionsExpirationExposureSummary], list[str]]:
    groups: dict[str, list[OptionContractStructureRow]] = defaultdict(list)
    for contract in snapshot.contracts:
        groups[str(contract.expiration or "")].append(contract)

    summaries: list[OptionsExpirationExposureSummary] = []
    missing_inputs: list[str] = []
    for expiration, contracts in sorted(groups.items(), key=lambda item: (_dte_sort_value(item[0], snapshot.as_of), item[0])):
        group_missing_inputs: list[str] = []
        call_contracts = [contract for contract in contracts if contract.side == "call"]
        put_contracts = [contract for contract in contracts if contract.side == "put"]
        exposures: list[float | None] = []
        for contract in contracts:
            exposure, missing = _contract_gamma_exposure(contract, spot_price=snapshot.spot_price)
            exposures.append(exposure)
            missing_inputs.extend(missing)
            group_missing_inputs.extend(missing)
        exposure_count = sum(1 for value in exposures if value is not None)
        dte = _dte(expiration, snapshot.as_of)
        summaries.append(
            OptionsExpirationExposureSummary(
                expiration=expiration,
                dte=dte,
                isZeroDte=dte == 0,
                strikeCount=len({float(contract.strike) for contract in contracts}),
                contractCount=len(contracts),
                callOpenInterest=_safe_sum(contract.open_interest for contract in call_contracts),
                putOpenInterest=_safe_sum(contract.open_interest for contract in put_contracts),
                callVolume=_safe_sum(contract.volume for contract in call_contracts),
                putVolume=_safe_sum(contract.volume for contract in put_contracts),
                netDealerGammaExposure=_round_optional(_combine_exposures(exposures)),
                calculationState=_calculation_state(len(contracts), exposure_count),
                missingInputs=_dedupe_codes(group_missing_inputs),
            )
        )
    return summaries, _dedupe_codes(missing_inputs)


def _nearest_expirations(snapshot: OptionChainSnapshot, *, limit: int = 3) -> list[OptionsNearestExpirationBucket]:
    buckets: dict[str, int] = defaultdict(int)
    for contract in snapshot.contracts:
        if contract.expiration:
            buckets[str(contract.expiration)] += 1
    ordered = sorted(buckets.items(), key=lambda item: (_dte_sort_value(item[0], snapshot.as_of), item[0]))
    return [
        OptionsNearestExpirationBucket(
            expiration=expiration,
            dte=_dte(expiration, snapshot.as_of),
            contractCount=count,
        )
        for expiration, count in ordered[:limit]
    ]


def _zero_dte_bucket(
    expiration_summaries: list[OptionsExpirationExposureSummary],
) -> OptionsZeroDteConcentration:
    total_oi = sum(item.call_open_interest + item.put_open_interest for item in expiration_summaries)
    total_volume = sum(item.call_volume + item.put_volume for item in expiration_summaries)
    bucket = next((item for item in expiration_summaries if item.dte == 0), None)
    if bucket is None:
        return OptionsZeroDteConcentration(state="not_available")
    bucket_oi = bucket.call_open_interest + bucket.put_open_interest
    bucket_volume = bucket.call_volume + bucket.put_volume
    return OptionsZeroDteConcentration(
        state="available",
        expiration=bucket.expiration,
        dte=bucket.dte,
        contractCount=bucket.contract_count,
        callOpenInterest=bucket.call_open_interest,
        putOpenInterest=bucket.put_open_interest,
        callVolume=bucket.call_volume,
        putVolume=bucket.put_volume,
        openInterestShare=round(bucket_oi / total_oi, 4) if total_oi else None,
        volumeShare=round(bucket_volume / total_volume, 4) if total_volume else None,
    )


def aggregate_options_structure_snapshot(snapshot: OptionChainSnapshot) -> OptionsStructureSummary:
    """Aggregate a caller-supplied options chain snapshot without inferring data."""

    strike_summaries, strike_missing = _summarize_strikes(snapshot)
    expiration_summaries, expiration_missing = _summarize_expirations(snapshot)
    all_missing = _dedupe_codes([*snapshot.missing_inputs, *strike_missing, *expiration_missing])
    total_gex = _combine_exposures(item.net_dealer_gamma_exposure for item in expiration_summaries)
    if not snapshot.contracts or total_gex is None:
        calculation_state = "not_available"
    elif any(item.calculation_state != "available" for item in strike_summaries):
        calculation_state = "degraded"
    else:
        calculation_state = "available"
    if not snapshot.contracts:
        status = "not_available"
    elif calculation_state == "available" and not all_missing:
        status = "available"
    else:
        status = "degraded"

    blocking_reasons = list(all_missing)
    if not snapshot.contracts:
        blocking_reasons.append("missing_option_chain_snapshot")
    if total_gex is None and snapshot.contracts:
        blocking_reasons.append("gex_calculation_not_available")
    blocking_reasons = _dedupe_codes(blocking_reasons)

    return OptionsStructureSummary(
        symbol=_normalize_symbol(snapshot.symbol),
        status=status,
        calculationState=calculation_state,
        observationOnly=True,
        decisionGrade=False,
        providerConfigured=True,
        spotPrice=snapshot.spot_price,
        asOf=snapshot.as_of,
        freshness=snapshot.freshness,
        snapshot=snapshot,
        strikeSummaries=strike_summaries,
        expirationSummaries=expiration_summaries,
        nearestExpirations=_nearest_expirations(snapshot),
        zeroDte=_zero_dte_bucket(expiration_summaries),
        gammaFlipLevel=OptionsGammaFlipLevel(),
        totalDealerGammaExposure=_round_optional(total_gex),
        blockingReasons=blocking_reasons,
        warnings=[],
        nextEvidenceNeeded=_next_evidence(blocking_reasons),
    )


def _next_evidence(blocking_reasons: list[str]) -> list[str]:
    items: list[str] = []
    if (
        OPTIONS_STRUCTURE_PROVIDER_MISSING_REASON in blocking_reasons
        or OPTIONS_STRUCTURE_PROVIDER_STATE_MISSING in blocking_reasons
    ):
        items.append("configure_authorized_options_structure_provider")
    if OPTIONS_STRUCTURE_PROVIDER_STATE_ENTITLEMENT_REQUIRED in blocking_reasons:
        items.append("obtain_options_structure_provider_entitlement")
    if "missing_option_chain_snapshot" in blocking_reasons:
        items.append("provide_option_chain_snapshot")
    if any(reason in blocking_reasons for reason in ("missing_gamma", "missing_open_interest", "missing_multiplier")):
        items.append("provide_greeks_open_interest_and_multiplier")
    if "missing_spot_price" in blocking_reasons:
        items.append("provide_spot_price")
    return _dedupe_codes(items)


def build_options_structure_not_available(
    symbol: str,
    *,
    provider_configured: bool = False,
    blocking_reasons: Iterable[str] | None = None,
) -> OptionsStructureSummary:
    normalized_symbol = _normalize_symbol(symbol)
    reasons = _consumer_safe_reason_codes(
        [
            *(blocking_reasons or []),
            OPTIONS_STRUCTURE_PROVIDER_MISSING_REASON if not provider_configured else "",
            OPTIONS_STRUCTURE_PROVIDER_STATE_MISSING if not provider_configured else "",
        ]
    )
    if not provider_configured and "missing_option_chain_snapshot" not in reasons:
        reasons.append("missing_option_chain_snapshot")
    snapshot = OptionChainSnapshot(
        symbol=normalized_symbol,
        spotPrice=None,
        asOf=None,
        freshness="not_available",
        contracts=[],
        missingInputs=list(reasons),
    )
    return OptionsStructureSummary(
        symbol=normalized_symbol,
        status="not_available",
        calculationState="not_available",
        observationOnly=True,
        decisionGrade=False,
        providerConfigured=provider_configured,
        spotPrice=None,
        asOf=None,
        freshness="not_available",
        snapshot=snapshot,
        strikeSummaries=[],
        expirationSummaries=[],
        nearestExpirations=[],
        zeroDte=OptionsZeroDteConcentration(state="not_available"),
        gammaFlipLevel=OptionsGammaFlipLevel(),
        totalDealerGammaExposure=None,
        blockingReasons=reasons,
        warnings=[],
        nextEvidenceNeeded=_next_evidence(reasons),
    )


def _normalize_expiration_filters(expiration_filters: Sequence[str] | None) -> tuple[str, ...]:
    return tuple(_dedupe_codes(str(item or "").strip() for item in (expiration_filters or []) if str(item or "").strip()))


def _filter_snapshot_expirations(
    snapshot: OptionChainSnapshot,
    expiration_filters: tuple[str, ...],
) -> OptionChainSnapshot:
    if not expiration_filters:
        return snapshot
    allowed = set(expiration_filters)
    contracts = [contract for contract in snapshot.contracts if contract.expiration in allowed]
    return snapshot.model_copy(update={"contracts": contracts})


def _provider_unavailable_summary(
    symbol: str,
    *,
    provider_configured: bool,
    reason_code: str,
    blocking_reasons: Iterable[str] | None = None,
) -> OptionsStructureSummary:
    safe_reason = (
        reason_code
        if reason_code in _SAFE_PROVIDER_UNAVAILABLE_REASONS
        else OPTIONS_STRUCTURE_PROVIDER_STATE_UNAVAILABLE
    )
    reasons = _consumer_safe_reason_codes([safe_reason, *(blocking_reasons or [])])
    if safe_reason == OPTIONS_STRUCTURE_PROVIDER_STATE_MISSING:
        reasons.append("missing_option_chain_snapshot")
    return build_options_structure_not_available(
        symbol,
        provider_configured=provider_configured,
        blocking_reasons=reasons,
    )


class OptionsStructureProviderGateway:
    """Fail-closed gateway between structure analytics and future providers."""

    def __init__(self, provider: OptionsStructureProvider | None = None) -> None:
        self.provider = provider

    def get_structure(
        self,
        symbol: str,
        *,
        as_of: str | None = None,
        expiration_filters: Sequence[str] | None = None,
    ) -> OptionsStructureSummary:
        normalized_symbol = _normalize_symbol(symbol)
        filters = _normalize_expiration_filters(expiration_filters)
        if self.provider is None:
            return _provider_unavailable_summary(
                normalized_symbol,
                provider_configured=False,
                reason_code=OPTIONS_STRUCTURE_PROVIDER_STATE_MISSING,
            )

        request = OptionsStructureProviderRequest(
            symbol=normalized_symbol,
            as_of=str(as_of).strip() if as_of else None,
            expiration_filters=filters,
        )
        try:
            result = self.provider.fetch_options_structure(request)
        except Exception:
            return _provider_unavailable_summary(
                normalized_symbol,
                provider_configured=True,
                reason_code=OPTIONS_STRUCTURE_PROVIDER_STATE_UNAVAILABLE,
            )

        if isinstance(result, OptionsStructureProviderUnavailableResult):
            return _provider_unavailable_summary(
                normalized_symbol,
                provider_configured=True,
                reason_code=result.reason_code,
                blocking_reasons=result.blocking_reasons,
            )
        if not isinstance(result, OptionChainSnapshot):
            return _provider_unavailable_summary(
                normalized_symbol,
                provider_configured=True,
                reason_code=OPTIONS_STRUCTURE_PROVIDER_STATE_UNAVAILABLE,
            )

        snapshot = result
        if _normalize_symbol(snapshot.symbol) != normalized_symbol:
            snapshot = snapshot.model_copy(update={"symbol": normalized_symbol})
        if request.as_of and not snapshot.as_of:
            snapshot = snapshot.model_copy(update={"as_of": request.as_of})
        snapshot = _filter_snapshot_expirations(snapshot, filters)
        return aggregate_options_structure_snapshot(snapshot)


class OptionsStructureService:
    """Service entry point for future professional options structure analytics."""

    def __init__(
        self,
        *,
        provider: OptionsStructureProvider | None = None,
        gateway: OptionsStructureProviderGateway | None = None,
    ) -> None:
        self.gateway = gateway or OptionsStructureProviderGateway(provider=provider)

    def get_structure(
        self,
        symbol: str,
        *,
        as_of: str | None = None,
        expiration_filters: Sequence[str] | None = None,
        snapshot: OptionChainSnapshot | None = None,
    ) -> OptionsStructureSummary:
        if snapshot is None:
            return self.gateway.get_structure(
                symbol,
                as_of=as_of,
                expiration_filters=expiration_filters,
            )
        if _normalize_symbol(snapshot.symbol) != _normalize_symbol(symbol):
            snapshot = snapshot.model_copy(update={"symbol": _normalize_symbol(symbol)})
        return aggregate_options_structure_snapshot(snapshot)


__all__ = [
    "OPTIONS_STRUCTURE_PROVIDER_MISSING_REASON",
    "OPTIONS_STRUCTURE_PROVIDER_STATE_ENTITLEMENT_REQUIRED",
    "OPTIONS_STRUCTURE_PROVIDER_STATE_MISSING",
    "OPTIONS_STRUCTURE_PROVIDER_STATE_UNAVAILABLE",
    "OptionsStructureProvider",
    "OptionsStructureProviderGateway",
    "OptionsStructureProviderRequest",
    "OptionsStructureProviderUnavailableResult",
    "OptionsStructureProviderResult",
    "OptionsStructureService",
    "aggregate_options_structure_snapshot",
    "build_options_structure_not_available",
]
