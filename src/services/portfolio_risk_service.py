# -*- coding: utf-8 -*-
"""Portfolio risk service for concentration, drawdown and stop-loss proximity."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any, Dict, List, Optional, Tuple

from src.config import Config, get_config
from src.repositories.portfolio_repo import PortfolioRepository
from src.services.portfolio_risk_board_lookup import PortfolioRiskBoardLookup
from src.services.portfolio_risk_diagnostics import build_portfolio_risk_diagnostics
from src.services.portfolio_service import PortfolioService


SECTOR_SOURCE_PROVENANCE_VERSION = "portfolio_sector_source_provenance_v1"
SECTOR_SOURCE_PROVENANCE_INTERNAL_FIELD = "_sectorSourceProvenance"


class PortfolioRiskService:
    """Compute portfolio risk blocks on top of replayed snapshot data."""

    def __init__(
        self,
        *,
        repo: Optional[PortfolioRepository] = None,
        portfolio_service: Optional[PortfolioService] = None,
        config: Optional[Config] = None,
        board_lookup: Optional[PortfolioRiskBoardLookup] = None,
    ):
        self.repo = repo or PortfolioRepository()
        self.portfolio_service = portfolio_service or PortfolioService(repo=self.repo)
        self.config = config or get_config()
        self._board_lookup = board_lookup or PortfolioRiskBoardLookup()

    def get_risk_report(
        self,
        *,
        account_id: Optional[int] = None,
        as_of: Optional[date] = None,
        cost_method: str = "fifo",
    ) -> Dict[str, Any]:
        as_of_date = as_of or date.today()
        snapshot = self.portfolio_service.get_portfolio_snapshot(
            account_id=account_id,
            as_of=as_of_date,
            cost_method=cost_method,
        )

        thresholds = {
            "concentration_alert_pct": float(getattr(self.config, "portfolio_risk_concentration_alert_pct", 35.0)),
            "drawdown_alert_pct": float(getattr(self.config, "portfolio_risk_drawdown_alert_pct", 15.0)),
            "stop_loss_alert_pct": float(getattr(self.config, "portfolio_risk_stop_loss_alert_pct", 10.0)),
            "stop_loss_near_ratio": float(getattr(self.config, "portfolio_risk_stop_loss_near_ratio", 0.8)),
            "lookback_days": int(getattr(self.config, "portfolio_risk_lookback_days", 180)),
        }

        concentration = self._build_concentration(
            snapshot,
            thresholds["concentration_alert_pct"],
            as_of_date=as_of_date,
        )
        sector_concentration = self._build_sector_concentration(
            snapshot,
            thresholds["concentration_alert_pct"],
            as_of_date=as_of_date,
        )
        industry_attribution = self._build_industry_attribution(
            snapshot=snapshot,
            as_of_date=as_of_date,
            include_sector_source_provenance=True,
        )
        sector_source_provenance = industry_attribution.pop(
            SECTOR_SOURCE_PROVENANCE_INTERNAL_FIELD,
            self._build_sector_source_provenance([]),
        )
        self._ensure_drawdown_snapshot_window(
            account_id=account_id,
            as_of_date=as_of_date,
            cost_method=cost_method,
            lookback_days=thresholds["lookback_days"],
        )
        drawdown = self._build_drawdown(
            account_id=account_id,
            as_of_date=as_of_date,
            cost_method=cost_method,
            threshold_pct=thresholds["drawdown_alert_pct"],
            lookback_days=thresholds["lookback_days"],
            report_currency=str(snapshot.get("currency") or "CNY"),
        )
        stop_loss = self._build_stop_loss(snapshot, thresholds)
        account_attribution = self._build_account_attribution(
            snapshot=snapshot,
            as_of_date=as_of_date,
        )
        diagnostics = build_portfolio_risk_diagnostics(
            portfolio_service=self.portfolio_service,
            snapshot=snapshot,
            account_id=account_id,
            as_of=as_of_date,
            cost_method=cost_method,
        )

        report = {
            "as_of": as_of_date.isoformat(),
            "account_id": account_id,
            "cost_method": cost_method,
            "currency": snapshot["currency"],
            "thresholds": thresholds,
            "concentration": concentration,
            "sector_concentration": sector_concentration,
            "industry_attribution": industry_attribution,
            "sectorSourceProvenance": sector_source_provenance,
            "drawdown": drawdown,
            "stop_loss": stop_loss,
            "account_attribution": account_attribution,
        }
        report.update(diagnostics)
        return report

    def _ensure_drawdown_snapshot_window(
        self,
        *,
        account_id: Optional[int],
        as_of_date: date,
        cost_method: str,
        lookback_days: int,
    ) -> None:
        if lookback_days <= 0:
            return

        start_date = self._resolve_backfill_start_date(
            account_id=account_id,
            as_of_date=as_of_date,
            lookback_days=lookback_days,
        )
        if start_date > as_of_date:
            return

        existing_rows = self.repo.list_daily_snapshots_for_risk(
            as_of=as_of_date,
            cost_method=cost_method,
            account_id=account_id,
            lookback_days=lookback_days,
        )
        if account_id is not None:
            existing_dates = {row.snapshot_date for row in existing_rows if int(row.account_id) == int(account_id)}
            current_date = start_date
            while current_date <= as_of_date:
                if current_date not in existing_dates:
                    self.portfolio_service.get_portfolio_snapshot(
                        account_id=account_id,
                        as_of=current_date,
                        cost_method=cost_method,
                    )
                    existing_dates.add(current_date)
                current_date += timedelta(days=1)
            return

        account_ids = [int(account["id"]) for account in self.portfolio_service.list_accounts(include_inactive=False)]
        if not account_ids:
            return
        existing_pairs = {(int(row.account_id), row.snapshot_date) for row in existing_rows}
        current_date = start_date
        while current_date <= as_of_date:
            if not all((aid, current_date) in existing_pairs for aid in account_ids):
                self.portfolio_service.get_portfolio_snapshot(
                    account_id=None,
                    as_of=current_date,
                    cost_method=cost_method,
                )
                for aid in account_ids:
                    existing_pairs.add((aid, current_date))
            current_date += timedelta(days=1)

    def _resolve_backfill_start_date(
        self,
        *,
        account_id: Optional[int],
        as_of_date: date,
        lookback_days: int,
    ) -> date:
        window_start = as_of_date - timedelta(days=lookback_days)
        if account_id is not None:
            first_activity = self.repo.get_first_activity_date(account_id=account_id, as_of=as_of_date)
            return max(window_start, first_activity or as_of_date)

        first_activity_candidates: List[date] = []
        for account in self.portfolio_service.list_accounts(include_inactive=False):
            first_activity = self.repo.get_first_activity_date(account_id=int(account["id"]), as_of=as_of_date)
            if first_activity is not None:
                first_activity_candidates.append(first_activity)
        if not first_activity_candidates:
            return as_of_date
        return max(window_start, min(first_activity_candidates))

    def _build_concentration(self, snapshot: Dict[str, Any], threshold_pct: float, *, as_of_date: date) -> Dict[str, Any]:
        total_mv = float(snapshot.get("total_market_value", 0.0) or 0.0)
        report_currency = str(snapshot.get("currency") or "CNY")
        exposure_by_symbol: Dict[str, float] = {}
        for account in snapshot.get("accounts", []):
            for pos in account.get("positions", []):
                symbol = str(pos.get("symbol") or "").strip().upper()
                if not symbol:
                    continue
                market_value = float(pos.get("market_value_base") or 0.0)
                valuation_currency = str(pos.get("valuation_currency") or account.get("base_currency") or "CNY")
                converted, _, _ = self.portfolio_service.convert_amount(
                    amount=market_value,
                    from_currency=valuation_currency,
                    to_currency=report_currency,
                    as_of_date=as_of_date,
                )
                exposure_by_symbol[symbol] = exposure_by_symbol.get(symbol, 0.0) + converted

        rows = []
        for symbol, exposure in exposure_by_symbol.items():
            weight = (exposure / total_mv * 100.0) if total_mv > 0 else 0.0
            rows.append(
                {
                    "symbol": symbol,
                    "market_value_base": round(exposure, 6),
                    "weight_pct": round(weight, 4),
                    "is_alert": bool(weight >= threshold_pct),
                }
            )
        rows.sort(key=lambda item: item["market_value_base"], reverse=True)

        top_weight = rows[0]["weight_pct"] if rows else 0.0
        return {
            "total_market_value": round(total_mv, 6),
            "top_weight_pct": round(float(top_weight), 4),
            "alert": bool(top_weight >= threshold_pct),
            "top_positions": rows[:10],
        }

    def _build_sector_concentration(
        self,
        snapshot: Dict[str, Any],
        threshold_pct: float,
        *,
        as_of_date: date,
    ) -> Dict[str, Any]:
        total_mv, industry_rows, coverage, errors, _ = self._collect_industry_rows(
            snapshot=snapshot,
            as_of_date=as_of_date,
        )
        rows = []
        for item in industry_rows:
            rows.append(
                {
                    "sector": item["industry"],
                    "market_value_base": item["market_value_base"],
                    "weight_pct": item["weight_pct"],
                    "symbol_count": item["symbol_count"],
                    "is_alert": bool(float(item["weight_pct"]) >= threshold_pct),
                }
            )
        top_weight = rows[0]["weight_pct"] if rows else 0.0

        return {
            "total_market_value": round(total_mv, 6),
            "top_weight_pct": round(float(top_weight), 4),
            "alert": bool(top_weight >= threshold_pct),
            "top_sectors": rows[:10],
            "coverage": coverage,
            "errors": errors[:20],
        }

    def _build_industry_attribution(
        self,
        *,
        snapshot: Dict[str, Any],
        as_of_date: date,
        include_sector_source_provenance: bool = False,
    ) -> Dict[str, Any]:
        total_mv, rows, coverage, errors, provenance = self._collect_industry_rows(
            snapshot=snapshot,
            as_of_date=as_of_date,
            include_sector_source_provenance=include_sector_source_provenance,
        )
        payload = {
            "total_market_value": round(total_mv, 6),
            "top_industries": rows[:10],
            "coverage": coverage,
            "errors": errors[:20],
        }
        if include_sector_source_provenance:
            payload[SECTOR_SOURCE_PROVENANCE_INTERNAL_FIELD] = provenance
        return payload

    def _collect_industry_rows(
        self,
        *,
        snapshot: Dict[str, Any],
        as_of_date: date,
        include_sector_source_provenance: bool = False,
    ) -> Tuple[float, List[Dict[str, Any]], Dict[str, int], List[str], Dict[str, Any]]:
        total_mv = float(snapshot.get("total_market_value", 0.0) or 0.0)
        report_currency = str(snapshot.get("currency") or "CNY")
        industry_exposure: Dict[str, float] = {}
        industry_symbols: Dict[str, set] = {}
        coverage = {
            "classified_count": 0,
            "unclassified_count": 0,
            "failed_count": 0,
        }
        errors: List[str] = []
        board_cache: Dict[Tuple[str, str], Dict[str, Any]] = {}
        provenance_items: List[Dict[str, Any]] = []

        for account in snapshot.get("accounts", []):
            for pos in account.get("positions", []):
                symbol = str(pos.get("symbol") or "").strip().upper()
                market = str(pos.get("market") or account.get("market") or "").strip().lower()
                if not symbol:
                    continue

                market_value = float(pos.get("market_value_base") or 0.0)
                valuation_currency = str(pos.get("valuation_currency") or account.get("base_currency") or "CNY")
                converted, _, _ = self.portfolio_service.convert_amount(
                    amount=market_value,
                    from_currency=valuation_currency,
                    to_currency=report_currency,
                    as_of_date=as_of_date,
                )

                cache_key = (symbol, market)
                was_cached = cache_key in board_cache
                industry, provenance_item = self._resolve_primary_sector_with_provenance(
                    symbol=symbol,
                    market=market,
                    board_cache=board_cache,
                    coverage=coverage,
                    errors=errors,
                )
                if include_sector_source_provenance and not was_cached:
                    provenance_items.append(provenance_item)
                industry_exposure[industry] = industry_exposure.get(industry, 0.0) + converted
                industry_symbols.setdefault(industry, set()).add(symbol)

        rows: List[Dict[str, Any]] = []
        for industry, exposure in industry_exposure.items():
            weight = (exposure / total_mv * 100.0) if total_mv > 0 else 0.0
            rows.append(
                {
                    "industry": industry,
                    "market_value_base": round(exposure, 6),
                    "weight_pct": round(weight, 4),
                    "symbol_count": len(industry_symbols.get(industry, set())),
                }
            )
        rows.sort(key=lambda item: item["market_value_base"], reverse=True)
        return total_mv, rows, coverage, errors, self._build_sector_source_provenance(provenance_items)

    def _resolve_primary_sector(
        self,
        *,
        symbol: str,
        market: str,
        board_cache: Dict[Tuple[str, str], Dict[str, Any]],
        coverage: Dict[str, int],
        errors: List[str],
    ) -> str:
        sector, _ = self._resolve_primary_sector_with_provenance(
            symbol=symbol,
            market=market,
            board_cache=board_cache,
            coverage=coverage,
            errors=errors,
        )
        return sector

    def _resolve_primary_sector_with_provenance(
        self,
        *,
        symbol: str,
        market: str,
        board_cache: Dict[Tuple[str, str], Dict[str, Any]],
        coverage: Dict[str, int],
        errors: List[str],
    ) -> Tuple[str, Dict[str, Any]]:
        cache_key = (symbol, market)
        if cache_key in board_cache:
            cached = board_cache[cache_key]
            return str(cached.get("industryLabel") or "UNCLASSIFIED"), cached

        if market != "cn":
            coverage["unclassified_count"] += 1
            provenance = self._build_sector_source_provenance_item(
                symbol=symbol,
                market=market,
                industry_label="UNCLASSIFIED",
                classification_state="non_cn_not_applicable",
                source_kind="not_applicable",
                source_detail_state="not_applicable",
                detected_source_states=["not_applicable"],
                reason_codes=["non_cn_classification_not_applicable", "unclassified"],
            )
            board_cache[cache_key] = provenance
            return "UNCLASSIFIED", provenance

        try:
            boards = self._fetch_belong_boards(symbol)
            sector_name = self._pick_primary_board_name(boards)
            if sector_name:
                coverage["classified_count"] += 1
                detected_source_states = self._detect_board_source_states(boards)
                provenance = self._build_sector_source_provenance_item(
                    symbol=symbol,
                    market=market,
                    industry_label=sector_name,
                    classification_state="cn_board_lookup_resolved",
                    source_kind=self._primary_source_kind(detected_source_states, default="provider_observed"),
                    source_detail_state=self._board_source_detail_state(boards),
                    detected_source_states=detected_source_states,
                    reason_codes=["cn_board_lookup_resolved"],
                )
                board_cache[cache_key] = provenance
                return sector_name, provenance

            classification_state = "cn_board_lookup_empty" if not boards else "unresolved"
            detected_source_states = self._detect_board_source_states(boards)
            provenance = self._build_sector_source_provenance_item(
                symbol=symbol,
                market=market,
                industry_label="UNCLASSIFIED",
                classification_state=classification_state,
                source_kind=self._primary_source_kind(detected_source_states, default="missing"),
                source_detail_state=self._board_source_detail_state(boards),
                detected_source_states=detected_source_states,
                reason_codes=[classification_state, "unclassified"],
            )
        except Exception as exc:
            coverage["failed_count"] += 1
            errors.append(f"{symbol}: {exc}")
            provenance = self._build_sector_source_provenance_item(
                symbol=symbol,
                market=market,
                industry_label="UNCLASSIFIED",
                classification_state="lookup_failure",
                source_kind="unknown",
                source_detail_state="unknown",
                detected_source_states=["unknown"],
                reason_codes=["lookup_failed", "unclassified"],
            )

        coverage["unclassified_count"] += 1
        board_cache[cache_key] = provenance
        return "UNCLASSIFIED", provenance

    @staticmethod
    def _build_sector_source_provenance_item(
        *,
        symbol: str,
        market: str,
        industry_label: str,
        classification_state: str,
        source_kind: str,
        source_detail_state: str,
        detected_source_states: List[str],
        reason_codes: List[str],
    ) -> Dict[str, Any]:
        normalized_market = market or "unknown"
        normalized_label = industry_label or "UNCLASSIFIED"
        return {
            "symbol": symbol,
            "market": normalized_market,
            "sectorLabel": normalized_label,
            "industryLabel": normalized_label,
            "classificationState": classification_state,
            "sourceKind": source_kind,
            "sourceDetailState": source_detail_state,
            "detectedSourceStates": list(dict.fromkeys(detected_source_states)),
            "resolved": normalized_label != "UNCLASSIFIED",
            "boardLookupApplicable": normalized_market == "cn",
            "authorityGrant": False,
            "decisionGrade": False,
            "accountingMutation": False,
            "providerRoutingChanged": False,
            "externalProviderCallsAdded": False,
            "marketCacheMutation": False,
            "rawProviderPayloadStored": False,
            "reasonCodes": list(dict.fromkeys(reason_codes)),
        }

    @staticmethod
    def _build_sector_source_provenance(items: List[Dict[str, Any]]) -> Dict[str, Any]:
        sorted_items = sorted(
            items,
            key=lambda item: (
                str(item.get("market") or ""),
                str(item.get("symbol") or ""),
            ),
        )
        summary = {
            "symbolMarketCount": len(sorted_items),
            "resolvedCount": sum(1 for item in sorted_items if bool(item.get("resolved"))),
            "cnBoardLookupResolvedCount": sum(
                1 for item in sorted_items if item.get("classificationState") == "cn_board_lookup_resolved"
            ),
            "nonCnNotApplicableCount": sum(
                1 for item in sorted_items if item.get("classificationState") == "non_cn_not_applicable"
            ),
            "emptyBoardLookupCount": sum(
                1 for item in sorted_items if item.get("classificationState") == "cn_board_lookup_empty"
            ),
            "lookupFailureCount": sum(
                1 for item in sorted_items if item.get("classificationState") == "lookup_failure"
            ),
            "unresolvedCount": sum(1 for item in sorted_items if item.get("industryLabel") == "UNCLASSIFIED"),
            "fallbackOrProxySourceCount": sum(
                1 for item in sorted_items if item.get("sourceKind") in {"fallback", "proxy"}
            ),
            "providerObservedCount": sum(
                1
                for item in sorted_items
                if item.get("sourceKind") == "provider_observed"
                or "provider_observed" in list(item.get("detectedSourceStates") or [])
            ),
            "missingSourceDetailCount": sum(
                1 for item in sorted_items if item.get("sourceDetailState") in {"missing", "unknown"}
            ),
        }
        return {
            "provenanceVersion": SECTOR_SOURCE_PROVENANCE_VERSION,
            "diagnosticOnly": True,
            "observationOnly": True,
            "authorityGrant": False,
            "decisionGrade": False,
            "accountingMutation": False,
            "providerRoutingChanged": False,
            "externalProviderCallsAdded": False,
            "marketCacheMutation": False,
            "classificationAuthority": "not_authoritative",
            "summary": summary,
            "items": sorted_items,
        }

    @staticmethod
    def _detect_board_source_states(boards: List[Dict[str, Any]]) -> List[str]:
        if not boards:
            return ["missing"]

        states = {"provider_observed"}
        for item in boards:
            if not isinstance(item, dict):
                continue
            text = " ".join(f"{key}={value}" for key, value in item.items()).lower()
            if "fallback" in text or "回退" in text:
                states.add("fallback")
            if "proxy" in text or "代理" in text:
                states.add("proxy")
            if "missing" in text or "缺失" in text:
                states.add("missing")
        return sorted(states)

    @staticmethod
    def _primary_source_kind(states: List[str], *, default: str) -> str:
        for candidate in ("fallback", "proxy", "provider_observed", "missing", "unknown"):
            if candidate in states:
                return candidate
        return default

    @staticmethod
    def _board_source_detail_state(boards: List[Dict[str, Any]]) -> str:
        if not boards:
            return "missing"
        detail_keys = {
            "source",
            "source_name",
            "source_type",
            "provider",
            "data_source",
            "freshness",
            "freshness_status",
            "observed_at",
            "as_of",
        }
        for item in boards:
            if not isinstance(item, dict):
                continue
            if any(str(key).strip().lower() in detail_keys for key in item):
                return "present_not_authoritative"
        return "missing"

    def _fetch_belong_boards(self, symbol: str) -> List[Dict[str, Any]]:
        return self._board_lookup.fetch_belong_boards(symbol)

    @staticmethod
    def _pick_primary_board_name(boards: List[Dict[str, Any]]) -> Optional[str]:
        if not boards:
            return None

        preferred: Optional[str] = None
        fallback: Optional[str] = None
        for item in boards:
            if not isinstance(item, dict):
                continue
            name = str(item.get("name") or "").strip()
            if not name:
                continue
            if fallback is None:
                fallback = name
            type_text = str(item.get("type") or "").strip().lower()
            if "行业" in type_text or "industry" in type_text:
                preferred = name
                break
        return preferred or fallback

    def _build_drawdown(
        self,
        *,
        account_id: Optional[int],
        as_of_date: date,
        cost_method: str,
        threshold_pct: float,
        lookback_days: int,
        report_currency: str,
    ) -> Dict[str, Any]:
        rows = self.repo.list_daily_snapshots_for_risk(
            as_of=as_of_date,
            cost_method=cost_method,
            account_id=account_id,
            lookback_days=lookback_days,
        )
        if not rows:
            return {
                "series_points": 0,
                "max_drawdown_pct": 0.0,
                "current_drawdown_pct": 0.0,
                "alert": False,
                "fx_stale": False,
            }

        grouped: Dict[str, float] = {}
        stale_flag = False
        for row in rows:
            key = row.snapshot_date.isoformat()
            converted, stale, _ = self.portfolio_service.convert_amount(
                amount=float(row.total_equity or 0.0),
                from_currency=str(row.base_currency or "CNY"),
                to_currency=report_currency,
                as_of_date=row.snapshot_date,
            )
            grouped[key] = grouped.get(key, 0.0) + converted
            stale_flag = stale_flag or stale or bool(row.fx_stale)

        series: List[Tuple[str, float]] = sorted(grouped.items(), key=lambda item: item[0])
        peak = 0.0
        max_drawdown = 0.0
        current_drawdown = 0.0
        for _, equity in series:
            peak = max(peak, equity)
            if peak <= 0:
                drawdown = 0.0
            else:
                drawdown = (peak - equity) / peak * 100.0
            max_drawdown = max(max_drawdown, drawdown)
            current_drawdown = drawdown

        return {
            "series_points": len(series),
            "max_drawdown_pct": round(max_drawdown, 4),
            "current_drawdown_pct": round(current_drawdown, 4),
            "alert": bool(max_drawdown >= threshold_pct),
            "fx_stale": stale_flag,
        }

    def _build_account_attribution(
        self,
        *,
        snapshot: Dict[str, Any],
        as_of_date: date,
    ) -> Dict[str, Any]:
        report_currency = str(snapshot.get("currency") or "CNY")
        total_equity = float(snapshot.get("total_equity", 0.0) or 0.0)
        total_market_value = float(snapshot.get("total_market_value", 0.0) or 0.0)

        rows: List[Dict[str, Any]] = []
        for account in snapshot.get("accounts", []):
            converted_equity, stale_equity, _ = self.portfolio_service.convert_amount(
                amount=float(account.get("total_equity", 0.0) or 0.0),
                from_currency=str(account.get("base_currency") or report_currency),
                to_currency=report_currency,
                as_of_date=as_of_date,
            )
            converted_market_value, stale_market_value, _ = self.portfolio_service.convert_amount(
                amount=float(account.get("total_market_value", 0.0) or 0.0),
                from_currency=str(account.get("base_currency") or report_currency),
                to_currency=report_currency,
                as_of_date=as_of_date,
            )
            rows.append(
                {
                    "account_id": int(account.get("account_id")),
                    "account_name": str(account.get("account_name") or ""),
                    "market": str(account.get("market") or "").lower(),
                    "total_equity_base": round(float(converted_equity), 6),
                    "equity_weight_pct": round((float(converted_equity) / total_equity) * 100.0, 4) if total_equity > 0 else 0.0,
                    "total_market_value_base": round(float(converted_market_value), 6),
                    "market_value_weight_pct": round((float(converted_market_value) / total_market_value) * 100.0, 4) if total_market_value > 0 else 0.0,
                    "fx_stale": bool(account.get("fx_stale")) or stale_equity or stale_market_value,
                }
            )

        rows.sort(key=lambda item: (-float(item["total_equity_base"]), int(item["account_id"])))
        return {
            "total_equity": round(total_equity, 6),
            "total_market_value": round(total_market_value, 6),
            "top_accounts": rows[:20],
        }

    @staticmethod
    def _build_stop_loss(snapshot: Dict[str, Any], thresholds: Dict[str, Any]) -> Dict[str, Any]:
        stop_loss_pct = float(thresholds["stop_loss_alert_pct"])
        near_ratio = float(thresholds["stop_loss_near_ratio"])
        near_threshold = stop_loss_pct * near_ratio

        warnings: List[Dict[str, Any]] = []
        for account in snapshot.get("accounts", []):
            for pos in account.get("positions", []):
                avg_cost = float(pos.get("avg_cost", 0.0) or 0.0)
                last_price = float(pos.get("last_price", 0.0) or 0.0)
                if avg_cost <= 0:
                    continue
                loss_pct = max(0.0, (avg_cost - last_price) / avg_cost * 100.0)
                if loss_pct < near_threshold:
                    continue
                warnings.append(
                    {
                        "account_id": account.get("account_id"),
                        "symbol": pos.get("symbol"),
                        "avg_cost": round(avg_cost, 8),
                        "last_price": round(last_price, 8),
                        "loss_pct": round(loss_pct, 4),
                        "near_threshold_pct": round(near_threshold, 4),
                        "is_triggered": bool(loss_pct >= stop_loss_pct),
                    }
                )

        warnings.sort(key=lambda item: item["loss_pct"], reverse=True)
        return {
            "near_alert": len(warnings) > 0,
            "triggered_count": sum(1 for item in warnings if item["is_triggered"]),
            "near_count": len(warnings),
            "items": warnings[:20],
        }
