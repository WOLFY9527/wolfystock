# -*- coding: utf-8 -*-
"""Pure stock evidence packet projector.

The projector consumes already-built stock evidence payloads and emits a
deterministic packet for downstream prompt construction. It performs no
provider calls, SEC lookups, LLM calls, DB access, or endpoint wiring.
"""

from __future__ import annotations

from typing import Any, Mapping


STOCK_EVIDENCE_PACKET_SCHEMA_VERSION = "stock_evidence_packet_v1"
STOCK_EVIDENCE_CONFIDENCE_POLICY_VERSION = "stock_evidence_confidence_cap_v1"

EVIDENCE_CLASSES = (
    "quote",
    "technical",
    "fundamental",
    "news",
    "sec_filing_evidence",
)

_WEAK_PROVIDER_TOKENS = (
    "fallback",
    "placeholder",
    "unknown",
    "weak",
    "proxy",
    "synthetic",
)
_WEAK_FRESHNESS = {"stale", "fallback", "unknown", "missing", "delayed", "partial"}
_AVAILABLE_STATUSES = {"available", "ok", "success", "partial"}
_MISSING_STATUSES = {"", "missing", "unknown", "error", "unavailable", "rejected"}
_NEWS_PLACEHOLDER_TOKENS = ("placeholder", "unknown", "no recent headlines", "not available")
_SECRET_FIELD_TOKENS = (
    "secret",
    "token",
    "apikey",
    "api_key",
    "authorization",
    "cookie",
    "password",
    "credential",
    "header",
)


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _status(payload: Mapping[str, Any]) -> str:
    return _text(payload.get("status"), "missing").lower() or "missing"


def _provider(payload: Mapping[str, Any]) -> str:
    return _text(payload.get("provider") or payload.get("providerId") or payload.get("providerName"), "unknown")


def _as_of(payload: Mapping[str, Any]) -> str | None:
    for key in ("asOf", "updatedAt", "filedAt", "periodEndDate"):
        value = _text(payload.get(key))
        if value:
            return value
    return None


def _is_missing(payload: Mapping[str, Any]) -> bool:
    return _status(payload) in _MISSING_STATUSES


def _is_available(payload: Mapping[str, Any]) -> bool:
    return _status(payload) in _AVAILABLE_STATUSES and not _is_missing(payload)


def _is_weak_provider(payload: Mapping[str, Any]) -> bool:
    provider = _provider(payload).lower()
    source_type = _text(payload.get("sourceType") or payload.get("sourceClass") or payload.get("sourceTier")).lower()
    freshness = _text(payload.get("freshness") or payload.get("freshnessClass")).lower()
    if any(token in provider for token in _WEAK_PROVIDER_TOKENS):
        return True
    if source_type in {"fallback", "synthetic", "proxy", "unofficial_proxy", "missing"}:
        return True
    return freshness in _WEAK_FRESHNESS


def _news_is_placeholder(news: Mapping[str, Any]) -> bool:
    headline = _text(news.get("latestHeadline") or news.get("headline")).lower()
    provider = _provider(news).lower()
    if _status(news) in {"unknown", "missing", "placeholder", "unavailable", "error"}:
        return True
    return any(token in headline or token in provider for token in _NEWS_PLACEHOLDER_TOKENS)


def _append_gap(gaps: list[dict[str, Any]], evidence_class: str, reason_code: str, detail: str) -> None:
    gaps.append(
        {
            "evidenceClass": evidence_class,
            "reasonCode": reason_code,
            "detail": detail,
        }
    )


def _append_reason(reasons: list[str], reason_code: str) -> None:
    if reason_code not in reasons:
        reasons.append(reason_code)


def _confidence_label(value: int) -> str:
    if value >= 80:
        return "high"
    if value >= 60:
        return "medium"
    return "low"


def _source_ref_id(evidence_class: str, payload: Mapping[str, Any]) -> str:
    provider = _provider(payload).lower().replace(" ", "_") or "unknown"
    return f"{evidence_class}:{provider}"


def _source_ref(evidence_class: str, payload: Mapping[str, Any], *, observation_only: bool) -> dict[str, Any]:
    return {
        "sourceRefId": _source_ref_id(evidence_class, payload),
        "evidenceClass": evidence_class,
        "provider": _provider(payload),
        "status": _status(payload),
        "asOf": _as_of(payload),
        "sourceType": _text(
            payload.get("sourceType") or payload.get("sourceTier") or "local_or_reported",
            "local_or_reported",
        ),
        "freshness": _text(payload.get("freshness") or payload.get("freshnessClass") or "unknown", "unknown"),
        "observationOnly": observation_only,
        "scoreContributionAllowed": False if observation_only else bool(payload.get("scoreContributionAllowed", True)),
    }


def _required_item(
    evidence_class: str,
    payload: Mapping[str, Any],
    *,
    required: bool,
    observation_only: bool,
    reason_codes: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "evidenceClass": evidence_class,
        "required": required,
        "status": _status(payload),
        "sourceRefIds": [_source_ref_id(evidence_class, payload)],
        "asOf": _as_of(payload),
        "observationOnly": observation_only,
        "scoreContributionAllowed": False if observation_only else bool(payload.get("scoreContributionAllowed", True)),
        "reasonCodes": list(reason_codes or []),
    }


def _quote_support(quote: Mapping[str, Any]) -> dict[str, Any] | None:
    if not _is_available(quote):
        return None
    return {
        "evidenceClass": "quote",
        "sourceRefIds": [_source_ref_id("quote", quote)],
        "statement": "Quote snapshot is present, subject to the stated freshness and provider metadata.",
        "fields": {
            "price": quote.get("price"),
            "changePct": quote.get("changePct"),
            "currency": quote.get("currency"),
        },
    }


def _technical_support(technical: Mapping[str, Any]) -> dict[str, Any] | None:
    if not _is_available(technical):
        return None
    fields = {
        key: technical.get(key)
        for key in ("trend", "ma20", "rsi14", "support", "resistance")
        if technical.get(key) is not None
    }
    return {
        "evidenceClass": "technical",
        "sourceRefIds": [_source_ref_id("technical", technical)],
        "statement": "Technical snapshot is present with deterministic fields only.",
        "fields": fields,
    }


def _fundamental_support(fundamental: Mapping[str, Any]) -> dict[str, Any] | None:
    if not _is_available(fundamental):
        return None
    fields = {
        key: fundamental.get(key)
        for key in ("marketCap", "peTtm", "pb", "beta", "revenueTtm", "netIncomeTtm", "fcfTtm")
        if fundamental.get(key) is not None
    }
    return {
        "evidenceClass": "fundamental",
        "sourceRefIds": [_source_ref_id("fundamental", fundamental)],
        "statement": "Fundamental snapshot is present, without using observation-only SEC records as authority.",
        "fields": fields,
    }


def _news_support(news: Mapping[str, Any]) -> dict[str, Any] | None:
    if not _is_available(news) or _news_is_placeholder(news):
        return None
    return {
        "evidenceClass": "news",
        "sourceRefIds": [_source_ref_id("news", news)],
        "statement": "News headline is present and can be cited only as reported news evidence.",
        "fields": {"latestHeadline": news.get("latestHeadline") or news.get("headline")},
    }


def _sec_support(sec: Mapping[str, Any]) -> dict[str, Any] | None:
    if not sec:
        return None
    records = sec.get("records") if isinstance(sec.get("records"), list) else []
    forms: list[str] = []
    concepts: list[str] = []
    accessions: list[str] = []
    for record in records:
        record_payload = _as_mapping(record)
        for source, target in (
            (record_payload.get("form"), forms),
            (record_payload.get("concept"), concepts),
            (record_payload.get("accessionNumber"), accessions),
        ):
            text = _text(source)
            if text and text not in target:
                target.append(text)
    return {
        "evidenceClass": "sec_filing_evidence",
        "sourceRefIds": [_source_ref_id("sec_filing_evidence", sec)],
        "statement": "SEC filing sidecar provides observation-only filing metadata and is not scoring evidence.",
        "fields": {
            "recordCount": len(records),
            "forms": forms[:5],
            "concepts": concepts[:5],
            "accessionNumbers": accessions[:5],
        },
    }


def _blocked_boundary(claim: str, reason_code: str, detail: str) -> dict[str, Any]:
    return {"claim": claim, "allowed": False, "reasonCode": reason_code, "detail": detail}


def _allowed_boundary(claim: str, reason_code: str, detail: str) -> dict[str, Any]:
    return {"claim": claim, "allowed": True, "reasonCode": reason_code, "detail": detail}


def _has_secret_like_key(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = str(key).replace("-", "_").lower()
            if any(token in normalized for token in _SECRET_FIELD_TOKENS):
                return True
            if _has_secret_like_key(item):
                return True
    elif isinstance(value, list):
        return any(_has_secret_like_key(item) for item in value)
    return False


def _extract_item(payload: Mapping[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    meta = _as_mapping(payload.get("meta"))
    items = payload.get("items")
    if isinstance(items, list) and items:
        return _as_mapping(items[0]), meta
    return _as_mapping(payload), meta


def _packet_as_of(item: Mapping[str, Any], meta: Mapping[str, Any]) -> str | None:
    meta_as_of = _text(meta.get("generatedAt") or meta.get("asOf"))
    if meta_as_of:
        return meta_as_of
    for key in ("quote", "technical", "fundamental", "news", "secFilingEvidence"):
        as_of = _as_of(_as_mapping(item.get(key)))
        if as_of:
            return as_of
    return None


def project_stock_evidence_packet(stock_evidence_payload: Mapping[str, Any]) -> dict[str, Any]:
    """Project an existing stock evidence payload into a deterministic packet."""

    item, meta = _extract_item(stock_evidence_payload)
    symbol = _text(item.get("symbol"), "unknown").upper() or "unknown"
    market = _text(item.get("market"), "unknown") or "unknown"
    quote = _as_mapping(item.get("quote"))
    technical = _as_mapping(item.get("technical"))
    fundamental = _as_mapping(item.get("fundamental"))
    news = _as_mapping(item.get("news"))
    sec = _as_mapping(item.get("secFilingEvidence"))

    data_gaps: list[dict[str, Any]] = []
    cap_reasons: list[str] = []
    confidence_cap = 90

    if _is_missing(quote):
        confidence_cap = min(confidence_cap, 35)
        _append_reason(cap_reasons, "missing_quote")
        _append_gap(data_gaps, "quote", "quote_missing", "Quote evidence is missing or unavailable.")
    if _is_missing(technical):
        confidence_cap = min(confidence_cap, 70)
        _append_reason(cap_reasons, "missing_technical")
        _append_gap(data_gaps, "technical", "technical_missing", "Technical evidence is missing or unavailable.")
    if _is_missing(fundamental):
        confidence_cap = min(confidence_cap, 65)
        _append_reason(cap_reasons, "missing_fundamental")
        _append_gap(data_gaps, "fundamental", "fundamental_missing", "Fundamental evidence is missing or unavailable.")
    elif fundamental.get("missingFields"):
        confidence_cap = min(confidence_cap, 65)
        _append_reason(cap_reasons, "partial_fundamental")
        _append_gap(data_gaps, "fundamental", "fundamental_partial", "Fundamental evidence has missing fields.")
    if _news_is_placeholder(news):
        confidence_cap = min(confidence_cap, 70)
        _append_reason(cap_reasons, "news_unknown_or_placeholder")
        _append_gap(
            data_gaps,
            "news",
            "news_unknown_or_placeholder",
            "News catalyst evidence is unknown or placeholder.",
        )

    weak_evidence = [
        evidence_class
        for evidence_class, payload in (
            ("quote", quote),
            ("technical", technical),
            ("fundamental", fundamental),
            ("news", news),
        )
        if payload and _is_weak_provider(payload)
    ]
    if weak_evidence:
        confidence_cap = min(confidence_cap, 55)
        _append_reason(cap_reasons, "weak_or_fallback_provider_evidence")

    sec_observation_only = bool(sec) and (
        sec.get("observationOnly") is not False or sec.get("scoreContributionAllowed") is False
    )
    if sec and not sec_observation_only:
        confidence_cap = min(confidence_cap, 50)
        _append_reason(cap_reasons, "sec_sidecar_authority_not_allowed")
        _append_gap(
            data_gaps,
            "sec_filing_evidence",
            "sec_sidecar_authority_not_allowed",
            "SEC sidecar attempted scoring authority.",
        )
    if sec and _has_secret_like_key(sec):
        _append_reason(cap_reasons, "unsafe_sec_fields_suppressed")

    source_refs = [
        _source_ref("quote", quote, observation_only=False),
        _source_ref("technical", technical, observation_only=False),
        _source_ref("fundamental", fundamental, observation_only=False),
        _source_ref("news", news, observation_only=False),
    ]
    if sec:
        source_refs.append(_source_ref("sec_filing_evidence", sec, observation_only=True))

    required_evidence = [
        _required_item("quote", quote, required=True, observation_only=False),
        _required_item("technical", technical, required=True, observation_only=False),
        _required_item("fundamental", fundamental, required=True, observation_only=False),
        _required_item("news", news, required=True, observation_only=False),
        _required_item(
            "sec_filing_evidence",
            sec or {"status": "missing", "providerId": "sec_edgar"},
            required=False,
            observation_only=True,
            reason_codes=["observation_only", "score_contribution_not_allowed"] if sec else ["not_supplied"],
        ),
    ]

    supporting_evidence = [
        support
        for support in (
            _quote_support(quote),
            _technical_support(technical),
            _fundamental_support(fundamental),
            _news_support(news),
            _sec_support(sec),
        )
        if support is not None
    ]

    score_eligible_evidence = [
        {
            "evidenceClass": evidence_class,
            "sourceRefIds": [_source_ref_id(evidence_class, payload)],
        }
        for evidence_class, payload in (
            ("quote", quote),
            ("technical", technical),
            ("fundamental", fundamental),
            ("news", news),
        )
        if (
            _is_available(payload)
            and not _is_weak_provider(payload)
            and not (evidence_class == "news" and _news_is_placeholder(payload))
        )
    ]
    observation_only_evidence = []
    if sec:
        observation_only_evidence.append(
            {
                "evidenceClass": "sec_filing_evidence",
                "sourceRefIds": [_source_ref_id("sec_filing_evidence", sec)],
                "reasonCodes": ["observation_only", "score_contribution_not_allowed"],
            }
        )
    if sec and not score_eligible_evidence:
        confidence_cap = min(confidence_cap, 45)
        _append_reason(cap_reasons, "observation_only_evidence_cannot_dominate")

    quote_live_allowed = (
        _is_available(quote)
        and _text(quote.get("sourceType")).lower() == "live"
        and _text(quote.get("freshness")).lower() == "fresh"
        and not _is_weak_provider(quote)
    )
    fundamentals_complete = (
        _is_available(fundamental)
        and not fundamental.get("missingFields")
        and not _is_weak_provider(fundamental)
    )
    news_catalyst_allowed = (
        _is_available(news)
        and not _news_is_placeholder(news)
        and not _is_weak_provider(news)
    )
    claim_boundaries = [
        _allowed_boundary(
            "price_is_live",
            "quote_live_freshness_proven",
            "Quote metadata explicitly says live and fresh.",
        )
        if quote_live_allowed
        else _blocked_boundary(
            "price_is_live",
            "quote_freshness_not_proven",
            "Quote status and freshness do not prove a live price.",
        ),
        _allowed_boundary(
            "fundamentals_are_complete",
            "fundamentals_complete",
            "Fundamental fields are present and not fallback-marked.",
        )
        if fundamentals_complete
        else _blocked_boundary(
            "fundamentals_are_complete",
            "fundamentals_missing_or_fallback",
            "Fundamental data is missing, partial, or fallback-marked.",
        ),
        _blocked_boundary(
            "sec_filing_supports_trading_signal",
            "sec_observation_only_non_scoring",
            "SEC filing sidecar is observation-only and cannot support trading signals.",
        ),
        _allowed_boundary(
            "news_catalyst_exists",
            "news_catalyst_evidence_present",
            "News headline evidence is present.",
        )
        if news_catalyst_allowed
        else _blocked_boundary(
            "news_catalyst_exists",
            "news_unknown_or_placeholder",
            "News is unknown, missing, weak, or placeholder.",
        ),
    ]

    if _is_missing(quote) or not score_eligible_evidence:
        thesis_status = "blocked"
    elif data_gaps or weak_evidence:
        thesis_status = "caution"
    else:
        thesis_status = "eligible"

    packet = {
        "schemaVersion": STOCK_EVIDENCE_PACKET_SCHEMA_VERSION,
        "symbol": symbol,
        "market": market,
        "asOf": _packet_as_of(item, meta),
        "thesisEligibility": {
            "status": thesis_status,
            "reasonCodes": list(cap_reasons),
        },
        "requiredEvidence": required_evidence,
        "supportingEvidence": supporting_evidence,
        "counterEvidence": [
            {
                "evidenceClass": evidence_class,
                "status": "not_evaluated",
                "reasonCode": "counter_evidence_placeholder",
            }
            for evidence_class in EVIDENCE_CLASSES
        ],
        "dataGaps": data_gaps,
        "sourceRefs": source_refs,
        "confidenceCap": {
            "value": max(0, min(100, confidence_cap)),
            "policyVersion": STOCK_EVIDENCE_CONFIDENCE_POLICY_VERSION,
            "reasonCodes": list(cap_reasons),
        },
        "confidenceLabel": _confidence_label(confidence_cap),
        "scoreEligibleEvidence": score_eligible_evidence,
        "observationOnlyEvidence": observation_only_evidence,
        "claimBoundaries": claim_boundaries,
        "promptSummary": (
            f"{symbol} evidence packet: "
            f"quote={_status(quote)}; technical={_status(technical)}; "
            f"fundamental={_status(fundamental)}; news={_status(news)}; "
            f"sec_filing_evidence={_status(sec) if sec else 'missing'}; "
            f"confidence_cap={max(0, min(100, confidence_cap))}; "
            f"thesis_eligibility={thesis_status}."
        ),
        "notInvestmentAdvice": True,
    }
    return packet


__all__ = [
    "EVIDENCE_CLASSES",
    "STOCK_EVIDENCE_CONFIDENCE_POLICY_VERSION",
    "STOCK_EVIDENCE_PACKET_SCHEMA_VERSION",
    "project_stock_evidence_packet",
]
