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
from src.services.stock_service_provider_adapter import StockServiceProviderAdapter
from src.services.us_history_helper import fetch_daily_history_with_local_us_fallback
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

            df, _source = fetch_daily_history_with_local_us_fallback(
                stock_code,
                days=fetch_days,
                manager=manager,
                log_context="[stock history]",
            )
            
            if df is None or df.empty:
                logger.warning(f"获取 {stock_code} 历史数据失败")
                return {"stock_code": stock_code, "period": period, "data": []}

            if period != "daily":
                df = self._aggregate_history_frame(df, period)
                if df.empty:
                    logger.warning(f"聚合 {stock_code} {period} 历史数据后为空")
                    return {"stock_code": stock_code, "period": period, "data": []}
            
            # 获取股票名称
            stock_name = manager.get_stock_name(stock_code)
            
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
            }
            
        except ImportError:
            logger.warning("DataFetcherManager 未找到，返回空数据")
            return {"stock_code": stock_code, "period": period, "data": []}
        except Exception as e:
            logger.error(f"获取历史数据失败: {e}", exc_info=True)
            return {"stock_code": stock_code, "period": period, "data": []}

    def get_intraday_data(
        self,
        stock_code: str,
        interval: str = "5m",
        range_period: str = "1d",
    ) -> Dict[str, Any]:
        """
        获取分钟级 / 日内行情，优先用于报告图表展示。
        """
        supported_intervals = {"1m", "2m", "5m", "15m", "30m", "60m", "90m"}
        supported_ranges = {"1d", "5d", "1mo"}
        if interval not in supported_intervals:
            raise ValueError(f"不支持的 interval 参数: {interval}")
        if range_period not in supported_ranges:
            raise ValueError(f"不支持的 range 参数: {range_period}")

        try:
            import yfinance as yf
            from data_provider.base import DataFetcherManager

            manager = DataFetcherManager()
            symbol = to_yfinance_symbol(stock_code)
            df = yf.download(
                tickers=symbol,
                period=range_period,
                interval=interval,
                progress=False,
                auto_adjust=True,
                prepost=True,
                multi_level_index=True,
            )
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
