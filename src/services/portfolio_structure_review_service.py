# -*- coding: utf-8 -*-
"""Read-only portfolio structure review projection."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from datetime import date
from typing import Any, Optional

from src.repositories.portfolio_repo import PortfolioRepository
from src.services.consumer_issue_labels import build_consumer_issues
from src.services.stock_structure_decision_engine import NO_ADVICE_DISCLOSURE
from src.services.stock_structure_decision_service import StockStructureDecisionService


PORTFOLIO_STRUCTURE_REVIEW_SCHEMA_VERSION = "portfolio_structure_review_v1"
DEFAULT_PORTFOLIO_STRUCTURE_REVIEW_COST_METHOD = "fifo"
_PORTFOLIO_STRUCTURE_SECTION = "portfolioStructureReview"
_RESEARCH_RADAR_SECTION = "topResearchPriorities"
_WATCHLIST_SECTION = "watchlistHighlights"
_SCENARIO_LAB_SECTION = "scenarioPresets"
_SAFE_RESEARCH_ROUTES = {
    "radar": "/research/radar",
    "watchlist": "/watchlist",
    "portfolio": "/portfolio",
    "scenario": "/market/scenario-lab",
}


class PortfolioStructureReviewService:
    """Compose cached portfolio holdings with stock structure observations.

    The service intentionally reads only owner-scoped accounts and cached
    snapshot bundles. It does not trigger portfolio replay, external workflows,
    imports, provider runtime changes, or snapshot writes.
    """

    def __init__(
        self,
        *,
        portfolio_repo: PortfolioRepository | None = None,
        structure_service: StockStructureDecisionService | None = None,
    ) -> None:
        self.portfolio_repo = portfolio_repo or PortfolioRepository()
        self.structure_service = structure_service or StockStructureDecisionService()

    def build_review(
        self,
        *,
        account_id: Optional[int] = None,
        as_of: Optional[date] = None,
        cost_method: str = DEFAULT_PORTFOLIO_STRUCTURE_REVIEW_COST_METHOD,
        benchmark: Optional[str] = None,
        max_items: Optional[int] = None,
        owner_id: Optional[str] = None,
    ) -> dict[str, Any]:
        method = _normalize_cost_method(cost_method)
        accounts = self._load_accounts(account_id=account_id, owner_id=owner_id)
        review_date = as_of or self._latest_cached_date(accounts, cost_method=method)

        missing_evidence: list[dict[str, str]] = []
        if not accounts:
            message = "Portfolio account is unavailable." if account_id is not None else "Active portfolio accounts are unavailable."
            missing_evidence.append(_missing("portfolio_account", message))
        if review_date is None:
            missing_evidence.append(_missing("cached_portfolio_holdings", "Cached portfolio holdings are unavailable."))

        cache_result = self._load_cached_holdings(
            accounts=accounts,
            review_date=review_date,
            cost_method=method,
            missing_evidence=missing_evidence,
        )
        valid_holdings = cache_result["validHoldings"]
        invalid_holdings = cache_result["invalidHoldings"]
        exposure_by_theme_or_sector = cache_result["exposureByThemeOrSector"]

        if not exposure_by_theme_or_sector:
            missing_evidence.append(
                _missing(
                    "theme_or_sector_exposure",
                    "Theme or sector exposure is unavailable from cached portfolio holdings.",
                )
            )

        batch_payload = self._build_structure_batch(
            valid_holdings,
            benchmark=benchmark,
            max_items=max_items,
            missing_evidence=missing_evidence,
        )
        structure_items_by_ticker = {
            str(item.get("ticker") or "").upper(): item
            for item in list(batch_payload.get("items") or [])
            if isinstance(item, Mapping)
        }

        holdings_structure = [
            _holding_structure_payload(holding, structure_items_by_ticker.get(holding["ticker"]))
            for holding in valid_holdings
        ]
        holdings_structure.extend(invalid_holdings)

        counts_by_state = _counts_by_structure_state(holdings_structure)
        data_quality = _data_quality(
            holdings=valid_holdings,
            invalid_holdings=invalid_holdings,
            accounts=accounts,
            missing_evidence=missing_evidence,
            batch_payload=batch_payload,
        )
        read_only = True
        fail_closed = bool(data_quality.get("failClosed"))
        consumer_state = _consumer_state(data_quality)
        research_linkage = _research_linkage(
            holdings_structure=holdings_structure,
            missing_evidence=missing_evidence,
        )

        return {
            "schemaVersion": PORTFOLIO_STRUCTURE_REVIEW_SCHEMA_VERSION,
            "aggregateSummary": _aggregate_summary(
                accounts=accounts,
                holdings=valid_holdings,
                invalid_holdings=invalid_holdings,
                review_date=review_date,
                batch_payload=batch_payload,
            ),
            "exposureByThemeOrSector": exposure_by_theme_or_sector,
            "countsByStructureState": counts_by_state,
            "holdingsStructure": holdings_structure,
            "strongestStructures": _safe_list(
                _safe_mapping(batch_payload.get("aggregateSummary")).get("strongestStructures")
            ),
            "weakestEvidence": _weakest_evidence(holdings_structure, batch_payload),
            "commonRiskFlags": _common_risk_flags(holdings_structure, batch_payload),
            "missingEvidence": _dedupe_missing(missing_evidence),
            "researchLinkage": research_linkage,
            "readOnly": read_only,
            "failClosed": fail_closed,
            "consumerState": consumer_state,
            "consumerSummary": _consumer_summary(consumer_state),
            "consumerMessage": _consumer_message(consumer_state),
            "drilldownSymbols": _drilldown_symbols(holdings_structure),
            "dataQuality": data_quality,
            "consumerIssues": build_consumer_issues(
                missing_evidence,
                data_quality,
                [item.get("missingEvidence") for item in holdings_structure],
                [item.get("riskFlags") for item in holdings_structure],
            ),
            "noAdviceDisclosure": str(batch_payload.get("noAdviceDisclosure") or NO_ADVICE_DISCLOSURE),
        }

    def _load_accounts(self, *, account_id: Optional[int], owner_id: Optional[str]) -> list[Any]:
        if account_id is not None:
            account = self.portfolio_repo.get_account(
                int(account_id),
                include_inactive=False,
                owner_id=owner_id,
                include_all_owners=False,
            )
            return [account] if account is not None else []
        return list(
            self.portfolio_repo.list_accounts(
                include_inactive=False,
                owner_id=owner_id,
                include_all_owners=False,
            )
        )

    def _latest_cached_date(self, accounts: Sequence[Any], *, cost_method: str) -> Optional[date]:
        dates: list[date] = []
        for account in accounts:
            account_id = _safe_int(getattr(account, "id", None))
            if account_id is None:
                continue
            cached_date = self.portfolio_repo.get_latest_cached_snapshot_date(
                account_id=account_id,
                cost_method=cost_method,
            )
            if isinstance(cached_date, date):
                dates.append(cached_date)
        return max(dates) if dates else None

    def _load_cached_holdings(
        self,
        *,
        accounts: Sequence[Any],
        review_date: Optional[date],
        cost_method: str,
        missing_evidence: list[dict[str, str]],
    ) -> dict[str, Any]:
        valid_holdings: list[dict[str, Any]] = []
        invalid_holdings: list[dict[str, Any]] = []
        exposure_by_theme_or_sector: list[dict[str, Any]] = []
        if review_date is None:
            return {
                "validHoldings": valid_holdings,
                "invalidHoldings": invalid_holdings,
                "exposureByThemeOrSector": exposure_by_theme_or_sector,
            }

        for account in accounts:
            account_id = _safe_int(getattr(account, "id", None))
            if account_id is None:
                invalid_holdings.append(_invalid_holding_payload())
                continue

            bundle = self.portfolio_repo.get_cached_snapshot_bundle(
                account_id=account_id,
                snapshot_date=review_date,
                cost_method=cost_method,
            )
            if not bundle:
                missing_evidence.append(_missing("cached_portfolio_holdings", "Cached portfolio holdings are unavailable."))
                continue

            snapshot = bundle.get("snapshot")
            positions = list(bundle.get("positions") or [])
            if not positions:
                missing_evidence.append(
                    _missing("cached_portfolio_holdings", "Cached portfolio holdings are unavailable.")
                )
                continue

            payload = _parse_snapshot_payload(getattr(snapshot, "payload", None))
            exposure_by_theme_or_sector.extend(_extract_theme_or_sector_exposure(payload))
            account_market_value = _to_float(getattr(snapshot, "total_market_value", None))

            for row in positions:
                holding = _holding_from_position(
                    row,
                    account=account,
                    account_market_value=account_market_value,
                )
                if holding is None:
                    invalid_holdings.append(_invalid_holding_payload())
                    missing_evidence.append(
                        _missing(
                            "security_metadata",
                            "Ticker, market, or currency metadata is missing for at least one cached holding.",
                        )
                    )
                    continue
                valid_holdings.append(holding)

        return {
            "validHoldings": valid_holdings,
            "invalidHoldings": invalid_holdings,
            "exposureByThemeOrSector": exposure_by_theme_or_sector,
        }

    def _build_structure_batch(
        self,
        holdings: Sequence[Mapping[str, Any]],
        *,
        benchmark: Optional[str],
        max_items: Optional[int],
        missing_evidence: list[dict[str, str]],
    ) -> dict[str, Any]:
        tickers = _unique_tickers([str(item.get("ticker") or "") for item in holdings])
        if not tickers:
            if holdings:
                missing_evidence.append(_missing("daily_ohlcv", "Daily OHLCV evidence is unavailable."))
            return {"items": [], "aggregateSummary": {}, "dataQuality": {"status": "unavailable"}}

        payload = self.structure_service.get_structure_decisions_batch(
            tickers,
            benchmark=benchmark,
            max_items=max_items,
        )
        if not isinstance(payload, Mapping):
            missing_evidence.append(_missing("structure_batch", "Structure review batch evidence is unavailable."))
            return {"items": [], "aggregateSummary": {}, "dataQuality": {"status": "unavailable"}}

        for item in _safe_list(payload.get("missingEvidence")):
            if isinstance(item, Mapping):
                missing_evidence.append(
                    _missing(str(item.get("kind") or "structure_evidence"), str(item.get("message") or ""))
                )
        return dict(payload)


def _normalize_cost_method(cost_method: str) -> str:
    method = str(cost_method or "").strip().lower()
    if method not in {"fifo", "avg"}:
        raise ValueError("cost_method must be fifo or avg")
    return method


def _holding_from_position(row: Any, *, account: Any, account_market_value: float) -> dict[str, Any] | None:
    ticker = str(getattr(row, "symbol", "") or "").strip().upper()
    market = str(getattr(row, "market", "") or "").strip().lower()
    currency = str(getattr(row, "currency", "") or "").strip().upper()
    if not ticker or not market or not currency:
        return None

    market_value = _to_float(getattr(row, "market_value_base", None))
    percent = round((market_value / account_market_value) * 100.0, 4) if account_market_value > 0 else None
    return {
        "ticker": ticker,
        "accountId": _safe_int(getattr(account, "id", None)),
        "market": market,
        "currency": currency,
        "marketValue": round(market_value, 6),
        "percent": percent,
    }


def _holding_structure_payload(holding: Mapping[str, Any], item: Mapping[str, Any] | None) -> dict[str, Any]:
    if not item:
        return {
            "ticker": str(holding.get("ticker") or ""),
            "structureState": "lowConfidence",
            "confidence": "low",
            "evidenceQuality": {"score": 0, "status": "unavailable"},
            "riskFlags": ["Structure evidence is unavailable for this cached holding."],
            "researchNotes": {
                "watchNext": [],
                "needsMoreEvidence": ["Daily OHLCV evidence is required before structure evidence can be reviewed."],
                "riskFlags": ["Structure evidence is unavailable for this cached holding."],
            },
            "missingEvidence": [
                _missing("daily_ohlcv", "Daily OHLCV evidence is unavailable for this cached holding.")
            ],
            "consumerIssues": build_consumer_issues(["daily_ohlcv"]),
        }

    component_scores = _safe_mapping(item.get("componentScores"))
    research_notes = _safe_mapping(item.get("researchNotes"))
    data_quality = _safe_mapping(item.get("dataQuality"))
    missing_evidence = [
        _missing(str(entry.get("kind") or "structure_evidence"), str(entry.get("message") or ""))
        for entry in _safe_list(item.get("missingEvidence"))
        if isinstance(entry, Mapping)
    ]
    risk_flags = [str(flag) for flag in _safe_list(research_notes.get("riskFlags"))]
    return {
        "ticker": str(item.get("ticker") or holding.get("ticker") or ""),
        "structureState": str(item.get("structureState") or "lowConfidence"),
        "confidence": str(item.get("confidence") or "low"),
        "evidenceQuality": {
            "score": int(component_scores.get("evidenceQuality") or 0),
            "status": str(data_quality.get("status") or "unavailable"),
        },
        "riskFlags": risk_flags,
        "researchNotes": {
            "watchNext": [str(note) for note in _safe_list(research_notes.get("watchNext"))],
            "needsMoreEvidence": [str(note) for note in _safe_list(research_notes.get("needsMoreEvidence"))],
            "riskFlags": risk_flags,
        },
        "missingEvidence": missing_evidence,
        "consumerIssues": build_consumer_issues(missing_evidence, risk_flags, data_quality),
    }


def _invalid_holding_payload() -> dict[str, Any]:
    risk_flags = ["Security metadata is unavailable for this cached holding."]
    return {
        "ticker": "UNKNOWN",
        "structureState": "lowConfidence",
        "confidence": "low",
        "evidenceQuality": {"score": 0, "status": "unavailable"},
        "riskFlags": risk_flags,
        "researchNotes": {
            "watchNext": [],
            "needsMoreEvidence": ["Security metadata is required before structure evidence can be reviewed."],
            "riskFlags": risk_flags,
        },
        "missingEvidence": [
            _missing("security_metadata", "Ticker, market, or currency metadata is missing for this cached holding.")
        ],
        "consumerIssues": build_consumer_issues(["security_metadata"]),
    }


def _aggregate_summary(
    *,
    accounts: Sequence[Any],
    holdings: Sequence[Mapping[str, Any]],
    invalid_holdings: Sequence[Mapping[str, Any]],
    review_date: Optional[date],
    batch_payload: Mapping[str, Any],
) -> dict[str, Any]:
    batch_summary = _safe_mapping(batch_payload.get("aggregateSummary"))
    return {
        "asOf": review_date.isoformat() if review_date is not None else None,
        "accountCount": len(accounts),
        "holdingCount": len(holdings) + len(invalid_holdings),
        "evaluatedCount": int(batch_summary.get("evaluatedCount") or len(_safe_list(batch_payload.get("items")))),
        "missingMetadataCount": len(invalid_holdings),
        "largestHolding": _largest_holding(holdings),
    }


def _largest_holding(holdings: Sequence[Mapping[str, Any]]) -> dict[str, Any] | None:
    if not holdings:
        return None
    ranked = sorted(
        holdings,
        key=lambda item: (
            -float(item.get("marketValue") or 0.0),
            str(item.get("ticker") or ""),
        ),
    )
    top = ranked[0]
    return {
        "ticker": str(top.get("ticker") or ""),
        "percent": top.get("percent"),
    }


def _counts_by_structure_state(holdings_structure: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in holdings_structure:
        state = str(item.get("structureState") or "lowConfidence")
        counts[state] = counts.get(state, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: item[0]))


def _weakest_evidence(holdings_structure: Sequence[Mapping[str, Any]], batch_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    batch_weakest = _safe_list(_safe_mapping(batch_payload.get("aggregateSummary")).get("weakestEvidence"))
    invalid = [
        {
            "ticker": str(item.get("ticker") or "UNKNOWN"),
            "status": str(_safe_mapping(item.get("evidenceQuality")).get("status") or "unavailable"),
            "usableBars": 0,
            "evidenceQuality": int(_safe_mapping(item.get("evidenceQuality")).get("score") or 0),
        }
        for item in holdings_structure
        if str(_safe_mapping(item.get("evidenceQuality")).get("status") or "") == "unavailable"
    ]
    return _safe_dict_rows(invalid + batch_weakest)[:3]


def _common_risk_flags(holdings_structure: Sequence[Mapping[str, Any]], batch_payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    batch_flags = _safe_list(_safe_mapping(batch_payload.get("aggregateSummary")).get("commonRiskFlags"))
    if batch_flags:
        return _safe_dict_rows(batch_flags)

    counts: dict[str, dict[str, Any]] = {}
    for item in holdings_structure:
        ticker = str(item.get("ticker") or "")
        for flag in _safe_list(item.get("riskFlags")):
            text = str(flag or "").strip()
            if not text:
                continue
            record = counts.setdefault(text, {"flag": text, "count": 0, "tickers": []})
            record["count"] += 1
            record["tickers"].append(ticker)
    return sorted(counts.values(), key=lambda entry: (-int(entry["count"]), str(entry["flag"])))[:5]


def _data_quality(
    *,
    holdings: Sequence[Mapping[str, Any]],
    invalid_holdings: Sequence[Mapping[str, Any]],
    accounts: Sequence[Any],
    missing_evidence: Sequence[Mapping[str, str]],
    batch_payload: Mapping[str, Any],
) -> dict[str, Any]:
    batch_quality = _safe_mapping(batch_payload.get("dataQuality"))
    structure_status = str(batch_quality.get("status") or "unavailable")
    holding_status = _holding_metadata_status(holdings, invalid_holdings, accounts)
    if not accounts or not holdings:
        status = "unavailable"
    elif invalid_holdings or structure_status in {"partial", "insufficient"}:
        status = "partial"
    elif structure_status == "unavailable":
        status = "unavailable"
    else:
        status = "available"
    return {
        "status": status,
        "holdingMetadataStatus": holding_status,
        "structureEvidenceStatus": structure_status,
        "availableStructureCount": int(batch_quality.get("availableCount") or 0),
        "partialStructureCount": int(batch_quality.get("partialCount") or 0),
        "insufficientStructureCount": int(batch_quality.get("insufficientCount") or 0),
        "unavailableStructureCount": int(batch_quality.get("unavailableCount") or 0),
        "readOnly": True,
        "failClosed": status == "unavailable" or bool(missing_evidence and not holdings),
    }


def _holding_metadata_status(
    holdings: Sequence[Mapping[str, Any]],
    invalid_holdings: Sequence[Mapping[str, Any]],
    accounts: Sequence[Any],
) -> str:
    if not accounts or (not holdings and invalid_holdings):
        return "unavailable"
    if invalid_holdings:
        return "partial"
    if holdings:
        return "available"
    return "unavailable"


def _extract_theme_or_sector_exposure(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    analytics = _safe_mapping(payload.get("analytics"))
    exposure = _safe_mapping(analytics.get("exposure"))
    sector_status = str(exposure.get("sector_status") or exposure.get("sectorStatus") or "")
    rows = _safe_list(exposure.get("by_sector") or exposure.get("bySector"))
    if sector_status == "unavailable" or not rows:
        return []
    return _safe_dict_rows(rows)


def _consumer_state(data_quality: Mapping[str, Any]) -> str:
    status = str(data_quality.get("status") or "unavailable").strip().lower()
    if status == "available":
        return "AVAILABLE"
    if status == "partial":
        return "PARTIAL"
    return "UNAVAILABLE"


def _consumer_summary(consumer_state: str) -> str:
    if consumer_state == "AVAILABLE":
        return "Structure review available"
    if consumer_state == "PARTIAL":
        return "Structure review partially available"
    return "Structure review unavailable"


def _consumer_message(consumer_state: str) -> str:
    if consumer_state == "AVAILABLE":
        return "Cached holdings and available structure evidence are shown in read-only mode."
    if consumer_state == "PARTIAL":
        return "Some holdings are missing metadata or structure evidence, so this review remains partial and read-only."
    return "Cached holdings or structure evidence are unavailable, so this panel remains fail-closed."


def _drilldown_symbols(holdings_structure: Sequence[Mapping[str, Any]]) -> list[str]:
    symbols: list[str] = []
    seen: set[str] = set()
    for item in holdings_structure:
        ticker = str(item.get("ticker") or "").strip().upper()
        if not ticker or ticker == "UNKNOWN" or ticker in seen:
            continue
        seen.add(ticker)
        symbols.append(ticker)
    return symbols


def _research_linkage(
    *,
    holdings_structure: Sequence[Mapping[str, Any]],
    missing_evidence: Sequence[Mapping[str, str]],
) -> dict[str, Any]:
    holding_drilldowns: list[dict[str, Any]] = []
    structure_links: list[dict[str, str]] = []
    radar_links: list[dict[str, str]] = []
    watchlist_links: list[dict[str, str]] = []
    scenario_links: list[dict[str, str]] = []
    unavailable_holdings = 0
    degraded_holdings = 0
    available_holdings = 0

    for item in holdings_structure:
        ticker = str(item.get("ticker") or "").strip().upper()
        if not ticker or ticker == "UNKNOWN":
            continue

        evidence_status = str(_safe_mapping(item.get("evidenceQuality")).get("status") or "unavailable").strip().lower()
        if evidence_status == "available":
            linkage_status = "available"
            available_holdings += 1
            degraded_linkage: list[dict[str, str]] = []
        elif evidence_status in {"partial", "insufficient"}:
            linkage_status = "degraded"
            degraded_holdings += 1
            degraded_linkage = [
                _degraded_linkage(
                    surface="stockStructure",
                    status="degraded",
                    reason="Structure evidence limited.",
                    message="Structure evidence is limited for this cached holding.",
                )
            ]
        else:
            linkage_status = "unavailable"
            unavailable_holdings += 1
            degraded_linkage = [
                _degraded_linkage(
                    surface="stockStructure",
                    status="unavailable",
                    reason="Structure evidence unavailable.",
                    message="Structure evidence is unavailable for this cached holding.",
                )
            ]

        structure = _structure_link(ticker)
        radar = _radar_link()
        watchlist = _watchlist_link()
        scenario = _scenario_link()
        holding_drilldowns.append(
            {
                "ticker": ticker,
                "structureLinks": [structure],
                "radarLinks": [radar],
                "watchlistLinks": [watchlist],
                "scenarioLinks": [scenario],
                "evidenceLinkage": linkage_status,
                "degradedLinkage": degraded_linkage,
            }
        )
        structure_links.append(structure)
        radar_links.append(radar)
        watchlist_links.append(watchlist)
        scenario_links.append(scenario)

    if holding_drilldowns:
        if unavailable_holdings or degraded_holdings:
            overall_status = "degraded"
        else:
            overall_status = "available"
        degraded_linkage = []
        if unavailable_holdings:
            degraded_linkage.append(
                _degraded_linkage(
                    surface="stockStructure",
                    status="unavailable",
                    reason="Structure evidence unavailable.",
                    message="Structure evidence is unavailable for at least one holding.",
                )
            )
        elif degraded_holdings:
            degraded_linkage.append(
                _degraded_linkage(
                    surface="stockStructure",
                    status="degraded",
                    reason="Structure evidence limited.",
                    message="Structure evidence is limited for at least one holding.",
                )
            )
    else:
        overall_status = "unavailable"
        degraded_linkage = [
            _degraded_linkage(
                surface="portfolioStructureReview",
                status="unavailable",
                reason="Portfolio holdings unavailable.",
                message="Cached holdings are unavailable, so linkage stays bounded.",
            )
        ]

    if not holding_drilldowns and any(str(item.get("kind") or "") == "security_metadata" for item in missing_evidence):
        degraded_linkage = [
            _degraded_linkage(
                surface="portfolioStructureReview",
                status="unavailable",
                reason="Portfolio holdings unavailable.",
                message="Cached holdings are unavailable, so linkage stays bounded.",
            )
        ]

    return {
        "status": overall_status,
        "holdingDrilldowns": holding_drilldowns,
        "structureLinks": _dedupe_link_targets(structure_links),
        "radarLinks": _dedupe_link_targets(radar_links),
        "watchlistLinks": _dedupe_link_targets(watchlist_links),
        "scenarioLinks": _dedupe_link_targets(scenario_links),
        "evidenceLinkage": {
            "status": overall_status,
            "availableHoldings": available_holdings,
            "degradedHoldings": degraded_holdings,
            "unavailableHoldings": unavailable_holdings,
        },
        "degradedLinkage": degraded_linkage,
    }


def _structure_link(ticker: str) -> dict[str, str]:
    return {
        "label": "Stock Structure",
        "route": f"/stocks/{ticker}/structure-decision",
        "section": _PORTFOLIO_STRUCTURE_SECTION,
        "reason": "Open symbol structure detail.",
    }


def _radar_link() -> dict[str, str]:
    return {
        "label": "Research Radar",
        "route": _SAFE_RESEARCH_ROUTES["radar"],
        "section": _RESEARCH_RADAR_SECTION,
        "reason": "Research radar queue context.",
    }


def _watchlist_link() -> dict[str, str]:
    return {
        "label": "Watchlist",
        "route": _SAFE_RESEARCH_ROUTES["watchlist"],
        "section": _WATCHLIST_SECTION,
        "reason": "Watchlist research context.",
    }


def _scenario_link() -> dict[str, str]:
    return {
        "label": "Scenario Lab",
        "route": _SAFE_RESEARCH_ROUTES["scenario"],
        "section": _SCENARIO_LAB_SECTION,
        "reason": "Compare scenario context for this holding.",
    }


def _degraded_linkage(*, surface: str, status: str, reason: str, message: str) -> dict[str, str]:
    return {
        "surface": surface,
        "status": status,
        "reason": reason,
        "message": message,
    }


def _dedupe_link_targets(items: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    result: list[dict[str, str]] = []
    seen: set[tuple[str, str, str, str]] = set()
    for item in items:
        label = str(item.get("label") or "").strip()
        route = str(item.get("route") or "").strip()
        section = str(item.get("section") or "").strip()
        reason = str(item.get("reason") or "").strip()
        if not label or not route or not section or not _is_safe_drilldown_route(route):
            continue
        key = (label, route, section, reason)
        if key in seen:
            continue
        seen.add(key)
        result.append(
            {
                "label": label,
                "route": route,
                "section": section,
                "reason": reason,
            }
        )
    return result


def _is_safe_drilldown_route(route: str) -> bool:
    if not route.startswith("/") or "://" in route or ".." in route or "?" in route:
        return False
    if route.startswith("/stocks/") and route.endswith("/structure-decision"):
        return True
    return route in _SAFE_RESEARCH_ROUTES.values()


def _parse_snapshot_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if not raw:
        return {}
    try:
        parsed = json.loads(str(raw))
    except Exception:
        return {}
    return dict(parsed) if isinstance(parsed, Mapping) else {}


def _missing(kind: str, message: str) -> dict[str, str]:
    return {"kind": kind, "message": message}


def _dedupe_missing(items: Sequence[Mapping[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str]] = set()
    result: list[dict[str, str]] = []
    for item in items:
        kind = str(item.get("kind") or "").strip()
        message = str(item.get("message") or "").strip()
        if not kind or not message:
            continue
        key = (kind, message)
        if key in seen:
            continue
        seen.add(key)
        result.append({"kind": kind, "message": message})
    return result


def _unique_tickers(tickers: Sequence[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for ticker in tickers:
        normalized = str(ticker or "").strip().upper()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        result.append(normalized)
    return result


def _safe_mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _safe_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []


def _safe_dict_rows(value: Sequence[Any]) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, Mapping)]


def _to_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
