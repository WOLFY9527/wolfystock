# -*- coding: utf-8 -*-
"""
===================================
API v1 路由聚合
===================================

职责：
1. 聚合 v1 版本的所有 endpoint 路由
2. 统一添加 /api/v1 前缀
"""

from fastapi import APIRouter

from api.v1.endpoints import analysis, auth, history, stocks, backtest, system_config, agent, usage, portfolio, admin_users, admin_portfolio, admin_security, admin_logs, admin_notifications, admin_cost, scanner, market_overview, market, market_provider_operations, watchlist, quant, options

# 创建 v1 版本主路由
router = APIRouter(prefix="/api/v1")

router.include_router(
    auth.router,
    prefix="/auth",
    tags=["Auth"]
)

router.include_router(
    agent.router,
    prefix="/agent",
    tags=["Agent"]
)

router.include_router(
    analysis.router,
    prefix="/analysis",
    tags=["Analysis"]
)

router.include_router(
    admin_users.router,
    prefix="/admin",
    tags=["AdminUsers"]
)

router.include_router(
    admin_portfolio.router,
    prefix="/admin",
    tags=["AdminPortfolio"]
)

router.include_router(
    admin_security.router,
    prefix="/admin",
    tags=["AdminSecurity"]
)

router.include_router(
    admin_logs.router,
    prefix="/admin/logs",
    tags=["AdminLogs"]
)

router.include_router(
    admin_notifications.router,
    prefix="/admin",
    tags=["AdminNotifications"]
)

router.include_router(
    admin_cost.router,
    prefix="/admin",
    tags=["AdminCost"]
)

router.include_router(
    market_provider_operations.router,
    prefix="/admin",
    tags=["MarketProviderOperations"]
)

router.include_router(
    history.router,
    prefix="/history",
    tags=["History"]
)

router.include_router(
    stocks.router,
    prefix="/stocks",
    tags=["Stocks"]
)

router.include_router(
    backtest.router,
    prefix="/backtest",
    tags=["Backtest"]
)

router.include_router(
    scanner.router,
    prefix="/scanner",
    tags=["Scanner"]
)

router.include_router(
    system_config.router,
    prefix="/system",
    tags=["SystemConfig"]
)

router.include_router(
    usage.router,
    prefix="/usage",
    tags=["Usage"]
)

router.include_router(
    portfolio.router,
    prefix="/portfolio",
    tags=["Portfolio"]
)

router.include_router(
    watchlist.router,
    prefix="/watchlist",
    tags=["Watchlist"]
)

router.include_router(
    market_overview.router,
    prefix="/market-overview",
    tags=["MarketOverview"]
)

router.include_router(
    market.router,
    prefix="/market",
    tags=["Market"]
)

router.include_router(
    quant.router,
    prefix="/quant",
    tags=["Quant"]
)

router.include_router(
    options.router,
    prefix="/options",
    tags=["OptionsLab"]
)
