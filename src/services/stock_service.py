# -*- coding: utf-8 -*-
"""
===================================
股票数据服务层
===================================

职责：
1. 封装股票数据获取逻辑
2. 提供实时行情和历史数据接口
"""

import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List

import pandas as pd

from src.repositories.stock_repo import StockRepository
from src.services.historical_ohlcv_readiness import (
    HistoricalOhlcvReadinessRequest,
    HistoricalOhlcvReadinessService,
)
from src.services.local_quote_snapshot_provider import LocalQuoteSnapshotJsonProvider
from src.services.quote_snapshot_config import get_configured_us_quote_snapshot_cache_path
from src.services.quote_snapshot_readiness import (
    DEFAULT_QUOTE_SNAPSHOT_MAX_AGE_SECONDS,
    QuoteSnapshotReadinessRequest,
    QuoteSnapshotReadinessService,
)
from src.services.source_confidence_contract import (
    SourceConfidenceContract,
    SourceFreshness,
    coerce_source_confidence_contract,
)
from src.services.starter_market_data import is_starter_market_data_symbol
from src.services.stock_service_provider_adapter import StockServiceProviderAdapter
from src.services.akshare_cn_ohlcv_cache import AkshareCnOhlcvRuntime, is_cn_a_share_symbol
from src.services.us_history_helper import LOCAL_US_PARQUET_SOURCE, fetch_daily_history_with_local_us_fallback
from src.services.uat_provider_isolation import (
    UAT_NO_LIVE_PROVIDERS_ENV,
    check_uat_provider_dispatch,
    uat_no_live_providers_enabled,
)
from src.utils.symbol_classification import is_us_stock_code
from src.utils.yfinance_symbol import to_yfinance_symbol

logger = logging.getLogger(__name__)


def _is_meaningful_stock_name(name: Optional[str], stock_code: str) -> bool:
    text = str(name or "").strip()
    normalized_code = str(stock_code or "").strip().upper()
    if not text:
        return False
    if text.lower() in {"unknown", "unnamed stock"}:
        return False
    if text == "待确认股票":
        return False
    if text.upper() == normalized_code:
        return False
    if text.startswith("股票"):
        return False
    return True


def _prepare_intraday_yfinance_request(
    stock_code: str,
    interval: str,
    range_period: str,
) -> tuple[str, Dict[str, Any]]:
    supported_intervals = {"1m", "2m", "5m", "15m", "30m", "60m", "90m"}
    supported_ranges = {"1d", "5d", "1mo"}
    if interval not in supported_intervals:
        raise ValueError(f"不支持的 interval 参数: {interval}")
    if range_period not in supported_ranges:
        raise ValueError(f"不支持的 range 参数: {range_period}")

    symbol = to_yfinance_symbol(stock_code)
    return symbol, {
        "tickers": symbol,
        "period": range_period,
        "interval": interval,
        "progress": False,
        "auto_adjust": True,
        "prepost": True,
        "multi_level_index": True,
    }


class StockService:
    """
    股票数据服务
    
    封装股票数据获取的业务逻辑
    """
    
    def __init__(self):
        """初始化股票数据服务"""
        self.repo = StockRepository()

    def validate_ticker_exists(self, stock_code: str) -> Dict[str, Any]:
        """Check whether the ticker resolves to a meaningful market entity."""
        normalized_code = str(stock_code or "").strip().upper()
        if not normalized_code:
            return {"stock_code": normalized_code, "exists": False, "stock_name": None}

        if uat_no_live_providers_enabled():
            return {"stock_code": normalized_code, "exists": False, "stock_name": None}

        try:
            adapter = StockServiceProviderAdapter()
            stock_name = adapter.get_stock_name(normalized_code, allow_realtime=False)
            if _is_meaningful_stock_name(stock_name, normalized_code):
                return {
                    "stock_code": normalized_code,
                    "exists": True,
                    "stock_name": str(stock_name).strip(),
                }

            quote = adapter.get_quote_snapshot(normalized_code)
            quote_name = quote.stock_name if quote is not None else None
            if _is_meaningful_stock_name(quote_name, normalized_code):
                return {
                    "stock_code": normalized_code,
                    "exists": True,
                    "stock_name": str(quote_name).strip(),
                }
        except ImportError:
            logger.warning("DataFetcherManager 未找到，无法执行股票代码真实性校验")
        except Exception as e:
            logger.warning("股票代码真实性校验失败 %s: %s", normalized_code, e)

        return {"stock_code": normalized_code, "exists": False, "stock_name": None}
    
    def get_realtime_quote(self, stock_code: str) -> Optional[Dict[str, Any]]:
        """
        获取股票实时行情
        
        Args:
            stock_code: 股票代码
            
        Returns:
            实时行情数据字典
        """
        observed_at = datetime.now().isoformat()
        if uat_no_live_providers_enabled():
            return self._get_consumer_safe_quote_recovery(stock_code, observed_at=observed_at)

        try:
            adapter = StockServiceProviderAdapter()
            quote = adapter.get_quote_snapshot(stock_code)
            
            if quote is None:
                logger.warning(f"获取 {stock_code} 实时行情失败")
                return self._get_consumer_safe_quote_recovery(stock_code, observed_at=observed_at)

            quote_metadata = self._build_quote_metadata(
                source=quote.source,
                market_timestamp=quote.market_timestamp,
                observed_at=observed_at,
                has_price=quote.current_price > 0,
            )
            return {
                "stock_code": quote.stock_code,
                "stock_name": quote.stock_name,
                "current_price": quote.current_price,
                "change": quote.change,
                "change_percent": quote.change_percent,
                "open": quote.open,
                "high": quote.high,
                "low": quote.low,
                "prev_close": quote.prev_close,
                "volume": quote.volume,
                "amount": quote.amount,
                "update_time": observed_at,
                "source": quote_metadata["source"],
                "source_type": quote_metadata["source_type"],
                "market_timestamp": quote_metadata["market_timestamp"],
                "observed_at": quote_metadata["observed_at"],
                "freshness": quote_metadata["freshness"],
                "is_fallback": quote_metadata["is_fallback"],
                "is_stale": quote_metadata["is_stale"],
                "is_partial": quote_metadata["is_partial"],
                "is_synthetic": quote_metadata["is_synthetic"],
                "sourceConfidence": quote_metadata["sourceConfidence"],
            }
            
        except ImportError:
            logger.warning("DataFetcherManager 未找到，返回结构化行情不可用状态")
            return self._get_consumer_safe_quote_recovery(stock_code, observed_at=observed_at)
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}", exc_info=True)
            return self._get_consumer_safe_quote_recovery(stock_code, observed_at=observed_at)

    def _get_consumer_safe_quote_recovery(
        self,
        stock_code: str,
        *,
        observed_at: str,
    ) -> Optional[Dict[str, Any]]:
        normalized_code = str(stock_code or "").strip().upper()
        if not is_us_stock_code(normalized_code) or not is_starter_market_data_symbol(normalized_code):
            return None

        cache_result = self._get_local_quote_snapshot_quote(normalized_code, observed_at=observed_at)
        if cache_result is not None:
            return cache_result
        return self._get_unavailable_quote_state(
            normalized_code,
            observed_at=observed_at,
            reason="quote_snapshot_missing",
        )

    def _get_local_quote_snapshot_quote(
        self,
        stock_code: str,
        *,
        observed_at: str,
    ) -> Optional[Dict[str, Any]]:
        cache_path = get_configured_us_quote_snapshot_cache_path()
        if cache_path is None:
            return None
        result = QuoteSnapshotReadinessService(
            provider=LocalQuoteSnapshotJsonProvider(cache_path=cache_path)
        ).fetch(
            QuoteSnapshotReadinessRequest(
                symbols=(stock_code,),
                market="us",
                max_age_seconds=DEFAULT_QUOTE_SNAPSHOT_MAX_AGE_SECONDS,
            )
        )
        if not result.snapshots:
            return None

        snapshot = result.snapshots[0]
        previous_close = snapshot.previous_close
        change = float(snapshot.last) - float(previous_close) if previous_close else None
        change_percent = (change / float(previous_close) * 100.0) if change is not None and previous_close else None
        source_confidence = SourceConfidenceContract(
            source=snapshot.source,
            source_label=str(snapshot.source or "Local quote snapshot cache").replace("_", " ").title(),
            as_of=snapshot.as_dict().get("asOf"),
            freshness=SourceFreshness.CACHED,
            is_fallback=True,
            confidence_weight=0.75,
            coverage=1.0,
            degradation_reason="local_quote_snapshot_cache",
        ).to_dict()
        return {
            "stock_code": snapshot.symbol,
            "stock_name": None,
            "current_price": float(snapshot.last),
            "change": change,
            "change_percent": change_percent,
            "open": None,
            "high": None,
            "low": None,
            "prev_close": previous_close,
            "volume": snapshot.volume,
            "amount": None,
            "update_time": observed_at,
            "source": snapshot.source,
            "source_type": "local_quote_snapshot_cache",
            "market_timestamp": snapshot.as_dict().get("asOf"),
            "observed_at": observed_at,
            "freshness": source_confidence["freshness"],
            "is_fallback": source_confidence["isFallback"],
            "is_stale": source_confidence["isStale"],
            "is_partial": source_confidence["isPartial"],
            "is_synthetic": source_confidence["isSynthetic"],
            "is_unavailable": source_confidence["isUnavailable"],
            "availability_state": result.readiness.get("availabilityState"),
            "provider_state": result.readiness.get("providerState"),
            "missing_requirements": result.readiness.get("missingRequirements") or [],
            "quoteReadiness": result.readiness,
            "sourceConfidence": source_confidence,
        }

    def _get_unavailable_quote_state(
        self,
        stock_code: str,
        *,
        observed_at: str,
        reason: str,
    ) -> Dict[str, Any]:
        readiness = QuoteSnapshotReadinessService().fetch(
            QuoteSnapshotReadinessRequest(symbols=(stock_code,), market="us")
        ).readiness
        missing_requirements = list(readiness.get("missingRequirements") or [])
        if reason not in missing_requirements:
            missing_requirements.append(reason)
        readiness = {
            **readiness,
            "missingRequirements": missing_requirements,
            "availabilityState": "missing",
            "freshnessState": "missing",
            "consumerSafe": True,
        }
        source_confidence = SourceConfidenceContract(
            source="unavailable",
            source_label="Quote unavailable",
            as_of=None,
            freshness=SourceFreshness.UNAVAILABLE,
            is_partial=True,
            is_unavailable=True,
            confidence_weight=0.0,
            coverage=0.0,
            degradation_reason=reason,
        ).to_dict()
        return {
            "stock_code": stock_code,
            "stock_name": None,
            "current_price": None,
            "change": None,
            "change_percent": None,
            "open": None,
            "high": None,
            "low": None,
            "prev_close": None,
            "volume": None,
            "amount": None,
            "update_time": observed_at,
            "source": "unavailable",
            "source_type": "unavailable",
            "market_timestamp": None,
            "observed_at": observed_at,
            "freshness": source_confidence["freshness"],
            "is_fallback": source_confidence["isFallback"],
            "is_stale": source_confidence["isStale"],
            "is_partial": source_confidence["isPartial"],
            "is_synthetic": source_confidence["isSynthetic"],
            "is_unavailable": source_confidence["isUnavailable"],
            "availability_state": "missing",
            "provider_state": readiness.get("providerState"),
            "missing_requirements": missing_requirements,
            "unavailable_reason": reason,
            "quoteReadiness": readiness,
            "sourceConfidence": source_confidence,
        }
    
    def get_history_data(
        self,
        stock_code: str,
        period: str = "daily",
        days: int = 90
    ) -> Dict[str, Any]:
        """
        获取股票历史行情
        
        Args:
            stock_code: 股票代码
            period: K 线周期 (daily/weekly/monthly)
            days: 获取天数
            
        Returns:
            历史行情数据字典
        """
        if period not in {"daily", "weekly", "monthly", "yearly"}:
            raise ValueError(f"不支持的周期参数: {period}")
        
        try:
            fetch_days = days
            if period == "weekly":
                fetch_days = max(days, 180)
            elif period == "monthly":
                fetch_days = max(days, 365)
            elif period == "yearly":
                fetch_days = max(days, 365 * 5)

            if uat_no_live_providers_enabled() and is_cn_a_share_symbol(stock_code):
                return self._build_provider_isolated_history_state(
                    stock_code=stock_code,
                    period=period,
                    requested_days=fetch_days,
                    unavailable_reason="provider_missing",
                )

            if is_cn_a_share_symbol(stock_code):
                return self._get_cn_history_data(
                    stock_code=stock_code,
                    period=period,
                    fetch_days=fetch_days,
                )

            # 调用数据获取器获取历史数据；UAT validation mode only reads local caches.
            manager = None
            if not uat_no_live_providers_enabled():
                from data_provider.base import DataFetcherManager

                manager = DataFetcherManager()

            df = None
            source = None
            fetch_error = None
            provider_trace: List[Dict[str, Any]] = []
            try:
                df, source = fetch_daily_history_with_local_us_fallback(
                    stock_code,
                    days=fetch_days,
                    manager=manager,
                    log_context="[stock history]",
                    allow_provider_fallback=not uat_no_live_providers_enabled(),
                )
                provider_trace = self._get_manager_daily_trace(manager)
            except Exception as exc:
                fetch_error = exc
                provider_trace = self._get_manager_daily_trace(manager)
                logger.warning("获取 %s 远端历史数据失败: %s", stock_code, exc)

            if df is None or df.empty:
                local_df, local_meta = self._load_recent_persisted_us_history(stock_code, fetch_days)
                if local_df is not None and not local_df.empty:
                    df = local_df
                    source = "local_db"
                    diagnostics = self._build_history_diagnostics(
                        status="degraded",
                        reason="provider_failed_local_db_fallback" if fetch_error else "provider_empty_local_db_fallback",
                        source=source,
                        rows=len(local_df),
                        requested_days=fetch_days,
                        provider_trace=provider_trace,
                        message="Provider history failed or returned empty; using persisted local daily OHLC rows.",
                        local_fallback=local_meta,
                        error=fetch_error,
                    )
                else:
                    logger.warning(f"获取 {stock_code} 历史数据失败")
                    diagnostics = self._build_history_diagnostics(
                        status="unavailable",
                        reason="us_daily_history_unavailable" if is_us_stock_code(stock_code) else "history_unavailable",
                        source="unavailable",
                        rows=0,
                        requested_days=fetch_days,
                        provider_trace=provider_trace,
                        message="No real OHLC daily history is currently available; callers should render an unavailable state.",
                        error=fetch_error,
                    )
                    return {
                        "stock_code": stock_code,
                        "stock_name": self._safe_get_stock_name(manager, stock_code),
                        "period": period,
                        "data": [],
                        "source": "unavailable",
                        "diagnostics": diagnostics,
                        "historicalOhlcvReadiness": self._build_history_ohlcv_readiness(
                            stock_code=stock_code,
                            period=period,
                            requested_days=fetch_days,
                            rows=[],
                            source_available=False,
                            unavailable_reason="provider_missing" if is_us_stock_code(stock_code) else "provider_unavailable",
                        ),
                        "sourceConfidence": self._build_history_source_confidence(
                            "unavailable",
                            rows=0,
                            requested_days=fetch_days,
                            diagnostics=diagnostics,
                        ),
                    }
            else:
                diagnostics = self._build_history_diagnostics(
                    status="ok",
                    reason="history_available",
                    source=source,
                    rows=len(df),
                    requested_days=fetch_days,
                    provider_trace=provider_trace,
                    message="Daily OHLC history is available.",
                )

            if period != "daily":
                df = self._aggregate_history_frame(df, period)
                if df.empty:
                    logger.warning(f"聚合 {stock_code} {period} 历史数据后为空")
                    diagnostics = self._build_history_diagnostics(
                        status="unavailable",
                        reason="history_aggregation_empty",
                        source="unavailable",
                        rows=0,
                        requested_days=fetch_days,
                        provider_trace=provider_trace,
                        message="Daily OHLC rows were present but aggregation produced no usable bars.",
                    )
                    return {
                        "stock_code": stock_code,
                        "stock_name": self._safe_get_stock_name(manager, stock_code),
                        "period": period,
                        "data": [],
                        "source": "unavailable",
                        "diagnostics": diagnostics,
                        "historicalOhlcvReadiness": self._build_history_ohlcv_readiness(
                            stock_code=stock_code,
                            period=period,
                            requested_days=fetch_days,
                            rows=[],
                            source_available=False,
                            unavailable_reason="provider_unavailable",
                        ),
                        "sourceConfidence": self._build_history_source_confidence(
                            "unavailable",
                            rows=0,
                            requested_days=fetch_days,
                            diagnostics=diagnostics,
                        ),
                    }
                diagnostics["rows"] = int(len(df))
            
            # 获取股票名称
            stock_name = self._safe_get_stock_name(manager, stock_code)
            
            # 转换为响应格式
            data = []
            for _, row in df.iterrows():
                date_val = row.get("date")
                if hasattr(date_val, "strftime"):
                    date_str = date_val.strftime("%Y-%m-%d")
                else:
                    date_str = str(date_val)
                
                data.append({
                    "date": date_str,
                    "open": float(row.get("open", 0)),
                    "high": float(row.get("high", 0)),
                    "low": float(row.get("low", 0)),
                    "close": float(row.get("close", 0)),
                    "volume": float(row.get("volume", 0)) if row.get("volume") else None,
                    "amount": float(row.get("amount", 0)) if row.get("amount") else None,
                    "change_percent": float(row.get("pct_chg", 0)) if row.get("pct_chg") else None,
                })
            
            return {
                "stock_code": stock_code,
                "stock_name": stock_name,
                "period": period,
                "data": data,
                "source": source or "unknown",
                "diagnostics": diagnostics,
                "historicalOhlcvReadiness": self._build_history_ohlcv_readiness(
                    stock_code=stock_code,
                    period=period,
                    requested_days=fetch_days,
                    rows=data,
                    source_available=bool(data) and str(source or "").lower() != "unavailable",
                ),
                "sourceConfidence": self._build_history_source_confidence(
                    source or "unknown",
                    rows=len(data),
                    requested_days=fetch_days,
                    diagnostics=diagnostics,
                ),
            }
            
        except ImportError:
            logger.warning("DataFetcherManager 未找到，返回空数据")
            diagnostics = self._build_history_diagnostics(
                status="unavailable",
                reason="provider_runtime_unavailable",
                source="unavailable",
                rows=0,
                requested_days=days,
                provider_trace=[],
                message="Provider runtime is unavailable.",
            )
            return {
                "stock_code": stock_code,
                "period": period,
                "data": [],
                "source": "unavailable",
                "diagnostics": diagnostics,
                "historicalOhlcvReadiness": self._build_history_ohlcv_readiness(
                    stock_code=stock_code,
                    period=period,
                    requested_days=days,
                    rows=[],
                    source_available=False,
                    unavailable_reason="provider_missing",
                ),
                "sourceConfidence": self._build_history_source_confidence(
                    "unavailable",
                    rows=0,
                    requested_days=days,
                    diagnostics=diagnostics,
                ),
            }

        except Exception as e:
            logger.error(f"获取历史数据失败: {e}", exc_info=True)
            diagnostics = self._build_history_diagnostics(
                status="unavailable",
                reason="history_request_failed",
                source="unavailable",
                rows=0,
                requested_days=days,
                provider_trace=[],
                message="History request failed before usable OHLC data could be returned.",
                error=e,
            )
            return {
                "stock_code": stock_code,
                "period": period,
                "data": [],
                "source": "unavailable",
                "diagnostics": diagnostics,
                "historicalOhlcvReadiness": self._build_history_ohlcv_readiness(
                    stock_code=stock_code,
                    period=period,
                    requested_days=days,
                    rows=[],
                    source_available=False,
                    unavailable_reason="provider_unavailable",
                ),
                "sourceConfidence": self._build_history_source_confidence(
                    "unavailable",
                    rows=0,
                    requested_days=days,
                    diagnostics=diagnostics,
                ),
            }

    def _build_provider_isolated_history_state(
        self,
        *,
        stock_code: str,
        period: str,
        requested_days: int,
        unavailable_reason: str,
    ) -> Dict[str, Any]:
        diagnostics = self._build_history_diagnostics(
            status="unavailable",
            reason="uat_no_live_providers",
            source="unavailable",
            rows=0,
            requested_days=requested_days,
            provider_trace=[],
            message="UAT validation mode disables live provider history reads; callers should render an unavailable state.",
        )
        return {
            "stock_code": stock_code,
            "stock_name": None,
            "period": period,
            "data": [],
            "source": "unavailable",
            "diagnostics": diagnostics,
            "historicalOhlcvReadiness": self._build_history_ohlcv_readiness(
                stock_code=stock_code,
                period=period,
                requested_days=requested_days,
                rows=[],
                source_available=False,
                unavailable_reason=unavailable_reason,
            ),
            "sourceConfidence": self._build_history_source_confidence(
                "unavailable",
                rows=0,
                requested_days=requested_days,
                diagnostics=diagnostics,
            ),
        }

    def _get_cn_history_data(self, *, stock_code: str, period: str, fetch_days: int) -> Dict[str, Any]:
        runtime_payload = AkshareCnOhlcvRuntime(repository=self.repo).get_history_data(
            stock_code=stock_code,
            period="daily",
            days=fetch_days,
        )
        data = runtime_payload.get("data") if isinstance(runtime_payload.get("data"), list) else []
        if not data:
            return {
                **runtime_payload,
                "stock_name": None,
                "period": period,
            }

        df = pd.DataFrame(data).rename(columns={"change_percent": "pct_chg"})
        if period != "daily":
            df = self._aggregate_history_frame(df, period)
        response_data = []
        for _, row in df.iterrows():
            date_val = row.get("date")
            if hasattr(date_val, "strftime"):
                date_str = date_val.strftime("%Y-%m-%d")
            else:
                date_str = str(date_val)
            item = {
                "date": date_str,
                "open": float(row.get("open", 0)),
                "high": float(row.get("high", 0)),
                "low": float(row.get("low", 0)),
                "close": float(row.get("close", 0)),
                "volume": float(row.get("volume", 0)) if row.get("volume") is not None else None,
                "amount": float(row.get("amount", 0)) if row.get("amount") is not None else None,
                "change_percent": float(row.get("pct_chg", 0)) if row.get("pct_chg") is not None else None,
            }
            adjusted_close = row.get("adjustedClose")
            if adjusted_close is not None:
                item["adjustedClose"] = float(adjusted_close)
            response_data.append(item)

        diagnostics = dict(runtime_payload.get("diagnostics") or {})
        diagnostics["rows"] = len(response_data)
        return {
            "stock_code": runtime_payload.get("stock_code") or stock_code,
            "stock_name": None,
            "period": period,
            "data": response_data,
            "source": runtime_payload.get("source") or "unknown",
            "diagnostics": diagnostics,
            "historicalOhlcvReadiness": self._build_history_ohlcv_readiness(
                stock_code=stock_code,
                period=period,
                requested_days=fetch_days,
                rows=response_data,
                source_available=bool(response_data),
            ),
            "sourceConfidence": runtime_payload.get("sourceConfidence") or {},
        }

    def get_intraday_data(
        self,
        stock_code: str,
        interval: str = "5m",
        range_period: str = "1d",
    ) -> Dict[str, Any]:
        """
        获取分钟级 / 日内行情，优先用于报告图表展示。
        """
        dispatch = check_uat_provider_dispatch(
            provider="yfinance",
            capability="intraday_history",
            route="StockService.get_intraday_data",
        )
        if not dispatch.allowed:
            metadata = self._build_intraday_metadata(
                source="unavailable",
                as_of=None,
                has_data=False,
                degradation_reason=dispatch.reason_code,
            )
            return {
                "stock_code": stock_code,
                "interval": interval,
                "range": range_period,
                "data": [],
                "source": metadata["source"],
                "source_type": metadata["source_type"],
                "freshness": metadata["freshness"],
                "is_fallback": metadata["is_fallback"],
                "is_stale": metadata["is_stale"],
                "is_partial": metadata["is_partial"],
                "is_synthetic": metadata["is_synthetic"],
                "is_unavailable": metadata["is_unavailable"],
                "sourceConfidence": metadata["sourceConfidence"],
                "reasonCode": dispatch.reason_code,
            }
        try:
            import yfinance as yf
            from data_provider.base import DataFetcherManager

            manager = DataFetcherManager()
            symbol, download_kwargs = _prepare_intraday_yfinance_request(
                stock_code,
                interval,
                range_period,
            )
            df = yf.download(**download_kwargs)
            if isinstance(df.columns, pd.MultiIndex):
                ticker_level = df.columns.get_level_values(-1)
                if (ticker_level == symbol).any():
                    df = df.loc[:, ticker_level == symbol].copy()
                df.columns = df.columns.get_level_values(0)

            if df is None or df.empty:
                logger.warning("获取 %s intraday 数据为空", stock_code)
                metadata = self._build_intraday_metadata(
                    source="yfinance",
                    as_of=None,
                    has_data=False,
                )
                return {
                    "stock_code": stock_code,
                    "stock_name": manager.get_stock_name(stock_code),
                    "interval": interval,
                    "range": range_period,
                    "data": [],
                    "source": metadata["source"],
                    "source_type": metadata["source_type"],
                    "freshness": metadata["freshness"],
                    "is_fallback": metadata["is_fallback"],
                    "is_stale": metadata["is_stale"],
                    "is_partial": metadata["is_partial"],
                    "is_synthetic": metadata["is_synthetic"],
                    "is_unavailable": metadata["is_unavailable"],
                    "sourceConfidence": metadata["sourceConfidence"],
                }

            df = df.reset_index()
            timestamp_column = next((col for col in df.columns if str(col).lower() in {"datetime", "date"}), None)
            if timestamp_column is None:
                raise ValueError("intraday 数据缺少时间列")

            data: List[Dict[str, Any]] = []
            for _, row in df.iterrows():
                timestamp = row.get(timestamp_column)
                if hasattr(timestamp, "isoformat"):
                    time_value = timestamp.isoformat()
                else:
                    time_value = str(timestamp)
                data.append({
                    "time": time_value,
                    "open": float(row.get("Open", 0)),
                    "high": float(row.get("High", 0)),
                    "low": float(row.get("Low", 0)),
                    "close": float(row.get("Close", 0)),
                    "volume": float(row.get("Volume", 0)) if row.get("Volume") is not None else None,
                })
            latest_timestamp = data[-1]["time"] if data else None
            metadata = self._build_intraday_metadata(
                source="yfinance",
                as_of=latest_timestamp,
                has_data=bool(data),
            )

            return {
                "stock_code": stock_code,
                "stock_name": manager.get_stock_name(stock_code),
                "interval": interval,
                "range": range_period,
                "data": data,
                "source": metadata["source"],
                "source_type": metadata["source_type"],
                "freshness": metadata["freshness"],
                "is_fallback": metadata["is_fallback"],
                "is_stale": metadata["is_stale"],
                "is_partial": metadata["is_partial"],
                "is_synthetic": metadata["is_synthetic"],
                "is_unavailable": metadata["is_unavailable"],
                "sourceConfidence": metadata["sourceConfidence"],
            }
        except ImportError:
            logger.warning("yfinance 不可用，无法获取 intraday 数据")
            metadata = self._build_intraday_metadata(
                source="unavailable",
                as_of=None,
                has_data=False,
            )
            return {
                "stock_code": stock_code,
                "interval": interval,
                "range": range_period,
                "data": [],
                "source": metadata["source"],
                "source_type": metadata["source_type"],
                "freshness": metadata["freshness"],
                "is_fallback": metadata["is_fallback"],
                "is_stale": metadata["is_stale"],
                "is_partial": metadata["is_partial"],
                "is_synthetic": metadata["is_synthetic"],
                "is_unavailable": metadata["is_unavailable"],
                "sourceConfidence": metadata["sourceConfidence"],
            }
        except Exception as e:
            logger.error(f"获取 intraday 数据失败: {e}", exc_info=True)
            metadata = self._build_intraday_metadata(
                source="error",
                as_of=None,
                has_data=False,
                degradation_reason="intraday_request_failed",
            )
            return {
                "stock_code": stock_code,
                "interval": interval,
                "range": range_period,
                "data": [],
                "source": metadata["source"],
                "source_type": metadata["source_type"],
                "freshness": metadata["freshness"],
                "is_fallback": metadata["is_fallback"],
                "is_stale": metadata["is_stale"],
                "is_partial": metadata["is_partial"],
                "is_synthetic": metadata["is_synthetic"],
                "is_unavailable": metadata["is_unavailable"],
                "sourceConfidence": metadata["sourceConfidence"],
            }

    def _aggregate_history_frame(self, df: pd.DataFrame, period: str) -> pd.DataFrame:
        if period == "daily":
            return df

        if "date" not in df.columns:
            return pd.DataFrame()

        frame = df.copy()
        frame["date"] = pd.to_datetime(frame["date"])
        frame = frame.sort_values("date")
        frame = frame.set_index("date")

        if period == "weekly":
            rule = "W-FRI"
        elif period == "monthly":
            rule = "ME"
        elif period == "yearly":
            rule = "YE"
        else:
            return frame.reset_index()
        aggregated = frame.resample(rule).agg(
            {
                "open": "first",
                "high": "max",
                "low": "min",
                "close": "last",
                "volume": "sum",
                "amount": "sum",
            }
        )
        aggregated = aggregated.dropna(subset=["open", "high", "low", "close"]).reset_index()
        aggregated["pct_chg"] = aggregated["close"].pct_change() * 100
        aggregated["pct_chg"] = aggregated["pct_chg"].fillna(0).round(2)
        aggregated["code"] = frame["code"].iloc[-1] if "code" in frame.columns and not frame.empty else None
        return aggregated

    def _load_recent_persisted_us_history(self, stock_code: str, days: int) -> tuple[pd.DataFrame, Dict[str, Any]]:
        normalized_code = str(stock_code or "").strip().upper()
        if not normalized_code or not is_us_stock_code(normalized_code):
            return pd.DataFrame(), {}

        rows = self.repo.get_recent_daily_rows(code=normalized_code, limit=max(1, int(days or 1)))
        records: List[Dict[str, Any]] = []
        sources = set()
        for row in reversed(list(rows or [])):
            record = {
                "date": getattr(row, "date", None),
                "open": getattr(row, "open", None),
                "high": getattr(row, "high", None),
                "low": getattr(row, "low", None),
                "close": getattr(row, "close", None),
                "volume": getattr(row, "volume", None),
                "amount": getattr(row, "amount", None),
                "pct_chg": getattr(row, "pct_chg", None),
                "code": normalized_code,
            }
            if any(pd.isna(record[field]) for field in ("date", "open", "high", "low", "close")):
                continue
            data_source = str(getattr(row, "data_source", "") or "").strip()
            if data_source:
                sources.add(data_source)
            records.append(record)

        if not records:
            return pd.DataFrame(), {}

        df = pd.DataFrame(records)
        df["date"] = pd.to_datetime(df["date"], errors="coerce")
        for column in ("open", "high", "low", "close", "volume", "amount", "pct_chg"):
            df[column] = pd.to_numeric(df[column], errors="coerce")
        df = df.dropna(subset=["date", "open", "high", "low", "close"]).sort_values("date").reset_index(drop=True)
        if df.empty:
            return pd.DataFrame(), {}

        latest_trade_date = df["date"].max().date().isoformat()
        return df, {
            "source": "local_db",
            "rows": int(len(df)),
            "latestTradeDate": latest_trade_date,
            "dataSources": sorted(sources),
        }

    @staticmethod
    def _get_manager_daily_trace(manager: Any) -> List[Dict[str, Any]]:
        getter = getattr(manager, "get_last_daily_history_trace", None)
        if not callable(getter):
            return []
        try:
            trace = getter()
        except Exception:
            return []
        return [dict(item) for item in trace if isinstance(item, dict)]

    @staticmethod
    def _safe_get_stock_name(manager: Any, stock_code: str) -> Optional[str]:
        getter = getattr(manager, "get_stock_name", None)
        if not callable(getter):
            return None
        try:
            return getter(stock_code)
        except Exception as exc:
            logger.warning("获取 %s 股票名称失败: %s", stock_code, exc)
            return None

    @staticmethod
    def _build_history_diagnostics(
        *,
        status: str,
        reason: str,
        source: Optional[str],
        rows: int,
        requested_days: int,
        provider_trace: List[Dict[str, Any]],
        message: str,
        local_fallback: Optional[Dict[str, Any]] = None,
        error: Optional[Exception] = None,
    ) -> Dict[str, Any]:
        diagnostics: Dict[str, Any] = {
            "status": status,
            "reason": reason,
            "message": message,
            "source": source or "unknown",
            "rows": int(rows or 0),
            "requestedDays": int(requested_days or 0),
            "providerTrace": provider_trace,
        }
        if local_fallback:
            diagnostics["localFallback"] = local_fallback
        if error is not None:
            diagnostics["error"] = " ".join(str(error).split())
        return diagnostics

    @staticmethod
    def _build_history_source_confidence(
        source: str,
        *,
        rows: int,
        requested_days: int,
        diagnostics: Dict[str, Any],
    ) -> Dict[str, Any]:
        normalized_source = str(source or "unknown").strip()
        status = str(diagnostics.get("status") or "").strip().lower()
        requested = max(1, int(requested_days or 1))
        coverage = min(1.0, max(0.0, float(rows or 0) / float(requested)))
        label_map = {
            LOCAL_US_PARQUET_SOURCE: "Local US parquet history",
            "local_db": "Persisted local daily history",
            "AlpacaFetcher": "Alpaca daily history",
            "YfinanceFetcher": "Yahoo Finance daily history",
            "unavailable": "Unavailable daily history",
        }
        if normalized_source == "unavailable" or status == "unavailable":
            freshness = SourceFreshness.UNAVAILABLE
            confidence_weight = 0.0
        elif normalized_source in {LOCAL_US_PARQUET_SOURCE, "local_db"}:
            freshness = SourceFreshness.CACHED
            confidence_weight = 0.85 if normalized_source == LOCAL_US_PARQUET_SOURCE else 0.75
        elif normalized_source == "AlpacaFetcher":
            freshness = SourceFreshness.DELAYED
            confidence_weight = 0.8
        elif normalized_source == "YfinanceFetcher":
            freshness = SourceFreshness.DELAYED
            confidence_weight = 0.7
        else:
            freshness = SourceFreshness.UNKNOWN
            confidence_weight = 0.5 if rows else 0.0

        contract = SourceConfidenceContract(
            source=normalized_source,
            source_label=label_map.get(normalized_source, normalized_source or "Unknown"),
            freshness=freshness,
            is_fallback=status == "degraded" or normalized_source in {LOCAL_US_PARQUET_SOURCE, "local_db"},
            is_unavailable=normalized_source == "unavailable" or status == "unavailable",
            confidence_weight=confidence_weight,
            coverage=round(coverage, 4),
            degradation_reason=str(diagnostics.get("reason") or "") or None,
        )
        return coerce_source_confidence_contract(contract).to_dict()

    @staticmethod
    def _build_history_ohlcv_readiness(
        *,
        stock_code: str,
        period: str,
        requested_days: int,
        rows: List[Dict[str, Any]],
        source_available: bool,
        unavailable_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        timeframe = "1d" if period == "daily" else period
        required_bars = max(0, int(requested_days or 0)) if period == "daily" else 0
        request = HistoricalOhlcvReadinessRequest(
            symbol=stock_code,
            market="US" if is_us_stock_code(stock_code) else "unknown",
            timeframe=timeframe,
            lookback_bars=max(0, int(requested_days or 0)),
            required_bars=required_bars,
            require_adjusted=False,
        )
        return HistoricalOhlcvReadinessService().assess_supplied_history(
            request,
            rows,
            source_available=bool(source_available),
            adjustments_available=None,
            unavailable_reason=unavailable_reason or ("provider_missing" if not source_available else None),
        ).readiness

    @staticmethod
    def _build_intraday_metadata(
        *,
        source: Optional[str],
        as_of: Optional[str],
        has_data: bool,
        degradation_reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        normalized_source = str(source or "").strip() or "unknown"
        normalized_as_of = str(as_of or "").strip() or None
        source_type = "provider_runtime"
        freshness = SourceFreshness.UNKNOWN
        is_partial = False
        is_unavailable = not has_data
        confidence_weight = 0.5 if has_data else 0.0
        source_label = normalized_source.replace("_", " ").title()
        coverage = 1.0 if has_data else 0.0

        if normalized_source in {"yfinance", "yfinance_proxy"}:
            source_type = "unofficial_proxy"
            source_label = "Yahoo Finance intraday proxy"
            freshness = SourceFreshness.DELAYED if has_data else SourceFreshness.UNAVAILABLE
            confidence_weight = 0.7 if has_data else 0.0
            degradation_reason = degradation_reason or ("delayed_source" if has_data else "provider_returned_empty_intraday")
        elif normalized_source == "unavailable":
            source_type = "unavailable"
            source_label = "Unavailable intraday history"
            freshness = SourceFreshness.UNAVAILABLE
            degradation_reason = degradation_reason or "provider_runtime_unavailable"
        elif normalized_source == "error":
            source_type = "error"
            source_label = "Intraday request error"
            freshness = SourceFreshness.UNAVAILABLE
            degradation_reason = degradation_reason or "intraday_request_failed"
        elif has_data:
            freshness = SourceFreshness.UNKNOWN
        else:
            freshness = SourceFreshness.UNAVAILABLE
            is_partial = True
            degradation_reason = degradation_reason or "intraday_data_unavailable"

        source_confidence = coerce_source_confidence_contract(
            SourceConfidenceContract(
                source=normalized_source,
                source_label=source_label,
                as_of=normalized_as_of,
                freshness=freshness,
                is_partial=is_partial,
                is_unavailable=is_unavailable,
                confidence_weight=confidence_weight,
                coverage=coverage,
                degradation_reason=degradation_reason,
            )
        ).to_dict()

        return {
            "source": normalized_source,
            "source_type": source_type,
            "freshness": source_confidence["freshness"],
            "is_fallback": source_confidence["isFallback"],
            "is_stale": source_confidence["isStale"],
            "is_partial": source_confidence["isPartial"],
            "is_synthetic": source_confidence["isSynthetic"],
            "is_unavailable": source_confidence["isUnavailable"],
            "sourceConfidence": source_confidence,
        }

    def _build_quote_metadata(
        self,
        *,
        source: Optional[str],
        market_timestamp: Optional[str],
        observed_at: str,
        has_price: bool,
        is_placeholder: bool = False,
    ) -> Dict[str, Any]:
        normalized_source = str(source or "").strip() or ("placeholder" if is_placeholder else "unknown")
        normalized_market_timestamp = str(market_timestamp or "").strip() or None
        source_type = "provider_runtime"
        freshness = SourceFreshness.UNKNOWN
        is_fallback = normalized_source == "fallback"
        is_partial = False
        is_synthetic = False
        confidence_weight = 0.5 if has_price else 0.0
        degradation_reason = None

        if is_placeholder:
            source_type = "synthetic_placeholder"
            freshness = SourceFreshness.SYNTHETIC
            is_partial = True
            is_synthetic = True
            confidence_weight = 0.0
            degradation_reason = "provider_runtime_unavailable_placeholder"
        elif is_fallback:
            source_type = "fallback"
            freshness = SourceFreshness.FALLBACK
            confidence_weight = 0.2 if has_price else 0.0
            degradation_reason = "provider_reported_fallback_source"
        elif normalized_market_timestamp:
            freshness = SourceFreshness.LIVE
            confidence_weight = 1.0 if has_price else 0.6
        else:
            is_partial = True
            degradation_reason = "market_timestamp_missing"

        source_confidence = SourceConfidenceContract(
            source=normalized_source,
            source_label=normalized_source.replace("_", " ").title(),
            as_of=normalized_market_timestamp,
            freshness=freshness,
            is_fallback=is_fallback,
            is_stale=freshness == SourceFreshness.STALE,
            is_partial=is_partial,
            is_synthetic=is_synthetic,
            confidence_weight=confidence_weight,
            degradation_reason=degradation_reason,
        ).to_dict()

        return {
            "source": normalized_source,
            "source_type": source_type,
            "market_timestamp": normalized_market_timestamp,
            "observed_at": observed_at,
            "freshness": source_confidence["freshness"],
            "is_fallback": source_confidence["isFallback"],
            "is_stale": source_confidence["isStale"],
            "is_partial": source_confidence["isPartial"],
            "is_synthetic": source_confidence["isSynthetic"],
            "sourceConfidence": source_confidence,
        }
    
    def _get_placeholder_quote(self, stock_code: str, *, observed_at: Optional[str] = None) -> Dict[str, Any]:
        """
        获取占位行情数据（用于测试）
        
        Args:
            stock_code: 股票代码
            
        Returns:
            占位行情数据
        """
        observed_time = observed_at or datetime.now().isoformat()
        quote_metadata = self._build_quote_metadata(
            source="placeholder",
            market_timestamp=None,
            observed_at=observed_time,
            has_price=False,
            is_placeholder=True,
        )
        return {
            "stock_code": stock_code,
            "stock_name": f"股票{stock_code}",
            "current_price": 0.0,
            "change": None,
            "change_percent": None,
            "open": None,
            "high": None,
            "low": None,
            "prev_close": None,
            "volume": None,
            "amount": None,
            "update_time": observed_time,
            "source": quote_metadata["source"],
            "source_type": quote_metadata["source_type"],
            "market_timestamp": quote_metadata["market_timestamp"],
            "observed_at": quote_metadata["observed_at"],
            "freshness": quote_metadata["freshness"],
            "is_fallback": quote_metadata["is_fallback"],
            "is_stale": quote_metadata["is_stale"],
            "is_partial": quote_metadata["is_partial"],
            "is_synthetic": quote_metadata["is_synthetic"],
            "sourceConfidence": quote_metadata["sourceConfidence"],
        }
