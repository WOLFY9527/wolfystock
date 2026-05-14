# -*- coding: utf-8 -*-
"""Pure provider diagnostics projection helpers for system config."""

from __future__ import annotations

from typing import Any, Dict, List, Optional


def provider_display_name(provider: str) -> str:
    return {
        "fmp": "FMP",
        "finnhub": "Finnhub",
        "alpha_vantage": "Alpha Vantage",
        "twelve_data": "Twelve Data",
        "tushare": "Tushare",
        "yahoo": "Yahoo/YFinance",
    }.get(provider, provider)


def mask_provider_secret(value: str) -> Optional[str]:
    secret = str(value or "").strip()
    if not secret:
        return None
    if "," in secret:
        parts = [part.strip() for part in secret.split(",") if part.strip()]
        if not parts:
            return None
        return f"{mask_provider_secret(parts[0])} (+{max(0, len(parts) - 1)})"
    if len(secret) <= 8:
        return f"{secret[:2]}...{secret[-2:]}" if len(secret) > 4 else "***"
    return f"{secret[:4]}...{secret[-4:]}"


def project_provider_result_checks(provider_result: Any) -> List[Dict[str, Any]]:
    metadata = provider_result.metadata if isinstance(getattr(provider_result, "metadata", None), dict) else {}
    raw_checks = metadata.get("checks") if isinstance(metadata.get("checks"), list) else []
    checks: List[Dict[str, Any]] = []
    for raw_check in raw_checks:
        if not isinstance(raw_check, dict):
            continue
        checks.append(
            {
                "name": str(raw_check.get("name") or ""),
                "endpoint": str(raw_check.get("endpoint") or ""),
                "ok": bool(raw_check.get("ok")),
                "http_status": raw_check.get("http_status"),
                "duration_ms": raw_check.get("duration_ms"),
                "error_type": raw_check.get("error_type"),
                "message": str(raw_check.get("message") or ""),
            }
        )
    return checks


def project_provider_result_status(provider_result: Any) -> str:
    status = str(getattr(getattr(provider_result, "status", None), "value", getattr(provider_result, "status", "")) or "")
    reason = str(getattr(getattr(provider_result, "reason", None), "value", getattr(provider_result, "reason", "")) or "")
    metadata = provider_result.metadata if isinstance(getattr(provider_result, "metadata", None), dict) else {}
    metadata_status = str(metadata.get("status") or "").strip().lower()
    if status == "success" and metadata_status == "partial":
        return "partial"
    if status == "success":
        return "success"
    if status == "skipped" and reason == "missing_api_key":
        return "missing_key"
    if status == "skipped" and reason == "unsupported_capability":
        return "unsupported"
    if status == "skipped":
        return "unsupported"
    return "failed"


def provider_validation_summary(provider: str, status: str, checks: List[Dict[str, Any]]) -> str:
    display = provider_display_name(provider)
    if status == "missing_key":
        return f"{display} 未配置 API key/token，无法执行远程校验。"
    if status == "unsupported":
        return "该 provider 暂未实现远程校验。"
    if provider == "fmp":
        if status == "success":
            return "FMP 连接成功：quote 和 historical endpoint 均可用。"
        if status == "partial":
            failed_names = ", ".join(str(check.get("name")) for check in checks if not check.get("ok"))
            return f"FMP 部分可用：部分 endpoint 失败。 失败 endpoint：{failed_names}。"
        return "FMP 连接失败：quote 和 historical endpoint 均不可用。"
    if provider == "finnhub":
        return "Finnhub 连接成功：quote endpoint 可用。" if status == "success" else "Finnhub 连接失败：quote endpoint 不可用。"
    if provider == "alpha_vantage":
        return "Alpha Vantage 连接成功：GLOBAL_QUOTE endpoint 可用。" if status == "success" else "Alpha Vantage 连接失败：GLOBAL_QUOTE endpoint 不可用。"
    if provider == "twelve_data":
        return "Twelve Data 连接成功：quote endpoint 可用。" if status == "success" else "Twelve Data 连接失败：quote endpoint 不可用。"
    if provider == "tushare":
        return "Tushare 连接成功：daily endpoint 可用。" if status == "success" else "Tushare 连接失败：daily endpoint 不可用。"
    if provider == "yahoo":
        return "Yahoo/YFinance 公共行情接口当前可用。" if status == "success" else "Yahoo/YFinance 公共行情接口当前不可用。"
    if status == "partial":
        failed_names = ", ".join(str(check.get("name")) for check in checks if not check.get("ok"))
        return f"{display} 部分可用。 失败 endpoint：{failed_names}。"
    return f"{display} 远程校验失败。"


def provider_validation_suggestion(provider: str, status: str) -> str:
    if status == "missing_key":
        return "请先在系统设置中保存该 provider 的 API key/token，然后重新校验。"
    if status == "unsupported":
        return "请改用已支持远程校验的 provider，或先通过该 provider 官方控制台确认凭据权限。"
    if provider == "fmp":
        return "请检查 FMP key 是否有效、套餐是否支持 quote/historical endpoint、额度是否用尽。"
    if provider == "finnhub":
        return "请检查 Finnhub token 是否有效、额度是否用尽，或当前套餐是否支持 quote endpoint。"
    if provider == "alpha_vantage":
        return "请检查 Alpha Vantage key 是否有效、是否触发频率限制，或切换到可用套餐。"
    if provider == "twelve_data":
        return "请检查 Twelve Data key 是否有效、额度是否用尽，或当前套餐是否支持 quote endpoint。"
    if provider == "tushare":
        return "请检查 Tushare token 是否有效、积分/权限是否支持 daily endpoint。"
    if provider == "yahoo":
        return "Yahoo/YFinance 是 public/unofficial 数据源；如失败，请稍后重试或配置带 key 的备用 provider。"
    return "请检查 provider 凭据、网络连通性和套餐权限后重试。"


_TICKFLOW_REASON_CODES = (
    "tickflow_not_configured",
    "tickflow_permission_unavailable",
    "tickflow_timeout",
    "tickflow_market_stats_empty",
    "tickflow_market_stats_malformed",
    "tickflow_unavailable",
)


def _normalize_tickflow_reason_code(*values: Any) -> Optional[str]:
    for value in values:
        text = str(value or "").strip().lower()
        if not text:
            continue
        for reason_code in _TICKFLOW_REASON_CODES:
            if reason_code in text:
                return reason_code
    return None


def project_tickflow_entitlement_health(
    *,
    api_key: Any,
    source: Any = None,
    source_type: Any = None,
    fallback_reason: Any = None,
    warning: Any = None,
    error_summary: Any = None,
) -> Dict[str, Any]:
    """Project read-only TickFlow entitlement and health diagnostics.

    This helper is metadata only. It must not call TickFlow, mutate config, or
    alter provider/runtime behavior.
    """

    normalized_source = str(source or "").strip().lower()
    normalized_source_type = str(source_type or "").strip() or None
    reason_code = _normalize_tickflow_reason_code(fallback_reason, warning, error_summary)

    credential_configured = bool(str(api_key or "").strip())
    if normalized_source == "tickflow" or (reason_code and reason_code != "tickflow_not_configured"):
        credential_configured = True

    credential_state = "configured" if credential_configured else "missing"
    reachability_state = "unknown"
    tickflow_reachable: Optional[bool] = None
    entitlement_state = "unknown"
    entitlement_usable: Optional[bool] = None
    status = "key_configured" if credential_configured else "key_missing"

    if normalized_source == "tickflow":
        reachability_state = "reachable"
        tickflow_reachable = True
        entitlement_state = "usable"
        entitlement_usable = True
        status = "breadth_entitlement_usable"
        reason_code = None
    elif reason_code == "tickflow_not_configured":
        credential_state = "missing"
        credential_configured = False
        status = "key_missing"
    elif reason_code == "tickflow_permission_unavailable":
        reachability_state = "reachable"
        tickflow_reachable = True
        entitlement_state = "permission_denied"
        entitlement_usable = False
        status = "permission_denied"
    elif reason_code == "tickflow_timeout":
        reachability_state = "timeout"
        tickflow_reachable = False
        status = "timeout"
    elif reason_code == "tickflow_market_stats_empty":
        reachability_state = "reachable"
        tickflow_reachable = True
        entitlement_state = "empty"
        entitlement_usable = False
        status = "empty"
    elif reason_code == "tickflow_market_stats_malformed":
        reachability_state = "reachable"
        tickflow_reachable = True
        entitlement_state = "malformed"
        entitlement_usable = False
        status = "malformed"
    elif reason_code == "tickflow_unavailable":
        reachability_state = "unreachable"
        tickflow_reachable = False
        status = "unreachable"

    summary = {
        "key_missing": "TickFlow key 未配置，无法评估 CN_Equity_A breadth entitlement。",
        "key_configured": "TickFlow key 已配置，但尚未观测到 CN_Equity_A breadth entitlement 结果。",
        "breadth_entitlement_usable": "TickFlow 可达，CN_Equity_A breadth entitlement 可用。",
        "permission_denied": "TickFlow key 已配置，但 CN_Equity_A breadth entitlement 当前无权限。",
        "timeout": "TickFlow key 已配置，但最近一次 CN_Equity_A breadth 检查超时。",
        "empty": "TickFlow 可达，但 CN_Equity_A breadth 返回空结果。",
        "malformed": "TickFlow 可达，但 CN_Equity_A breadth 返回格式异常。",
        "unreachable": "TickFlow key 已配置，但 TickFlow 当前不可达。",
    }[status]

    return {
        "provider": "tickflow",
        "market": "CN_Equity_A",
        "diagnosticTarget": "cn_breadth",
        "status": status,
        "credentialState": credential_state,
        "credentialConfigured": credential_configured,
        "reachabilityState": reachability_state,
        "tickflowReachable": tickflow_reachable,
        "breadthEntitlementState": entitlement_state,
        "breadthEntitlementUsable": entitlement_usable,
        "reasonCode": reason_code,
        "observedSource": normalized_source or None,
        "sourceType": normalized_source_type,
        "summary": summary,
    }
