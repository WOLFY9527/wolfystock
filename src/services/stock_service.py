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
from src.services.source_confidence_contract import SourceConfidenceContract, SourceFreshness
from src.services.stock_service_provider_adapter import StockServiceProviderAdapter
from src.services.us_history_helper import LOCAL_US_PARQUET_SOURCE, fetch_daily_history_with_local_us_fallback
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
        try:
            adapter = StockServiceProviderAdapter()
            quote = adapter.get_quote_snapshot(stock_code)
            
            if quote is None:
                logger.warning(f"获取 {stock_code} 实时行情失败")
                return None

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
                "update_time": datetime.now().isoformat(),
            }
            
        except ImportError:
            logger.warning("DataFetcherManager 未找到，使用占位数据")
            return self._get_placeholder_quote(stock_code)
        except Exception as e:
            logger.error(f"获取实时行情失败: {e}", exc_info=True)
            return None
    
    def get_history_data(
        self,
        stock_code: str,
        period: str = "daily",
        days: int = 30
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
            # 调用数据获取器获取历史数据
            from data_provider.base import DataFetcherManager
            
            manager = DataFetcherManager()
            fetch_days = days
            if period == "weekly":
                fetch_days = max(days, 180)
            elif period == "monthly":
                fetch_days = max(days, 365)
            elif period == "yearly":
                fetch_days = max(days, 365 * 5)

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
                "sourceConfidence": self._build_history_source_confidence(
                    "unavailable",
                    rows=0,
                    requested_days=days,
                    diagnostics=diagnostics,
                ),
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
                return {
                    "stock_code": stock_code,
                    "stock_name": manager.get_stock_name(stock_code),
                    "interval": interval,
                    "range": range_period,
                    "data": [],
                    "source": "yfinance",
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

            return {
                "stock_code": stock_code,
                "stock_name": manager.get_stock_name(stock_code),
                "interval": interval,
                "range": range_period,
                "data": data,
                "source": "yfinance",
            }
        except ImportError:
            logger.warning("yfinance 不可用，无法获取 intraday 数据")
            return {
                "stock_code": stock_code,
                "interval": interval,
                "range": range_period,
                "data": [],
                "source": "unavailable",
            }
        except Exception as e:
            logger.error(f"获取 intraday 数据失败: {e}", exc_info=True)
            return {
                "stock_code": stock_code,
                "interval": interval,
                "range": range_period,
                "data": [],
                "source": "error",
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
        return contract.to_dict()
    
    def _get_placeholder_quote(self, stock_code: str) -> Dict[str, Any]:
        """
        获取占位行情数据（用于测试）
        
        Args:
            stock_code: 股票代码
            
        Returns:
            占位行情数据
        """
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
            "update_time": datetime.now().isoformat(),
        }
