# -*- coding: utf-8 -*-
"""
===================================
分析服务层
===================================

职责：
1. 封装股票分析逻辑
2. 调用 analyzer 和 pipeline 执行分析
3. 保存分析结果到数据库
"""

import logging
import re
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, Callable, List, Iterable

from src.report_language import (
    get_sentiment_label,
    get_localized_stock_name,
    localize_operation_advice,
    localize_trend_prediction,
    normalize_report_language,
)
from src.utils.security import sanitize_message, sanitize_metadata
from src.utils.time_utils import to_beijing_iso8601
from src.services.research_readiness_contract import build_research_readiness_v1
from src.services.single_stock_evidence_packet import build_single_stock_evidence_packet_v1
from src.services.single_stock_fundamentals_earnings_normalizer import (
    build_single_stock_fundamentals_earnings_normalizer_v1,
)
from src.services.single_stock_news_catalyst_extractor import (
    build_single_stock_news_catalyst_extractor_v1,
)
from src.services.home_llm_evidence_input import build_home_llm_evidence_input_v1
from src.services.home_report_evidence_citations import (
    build_home_report_evidence_citation_frame_v1,
)
from src.services.home_source_provenance_sidecar import build_home_source_provenance_sidecar_v1
from src.services.intelligence_report_packet import build_intelligence_report_packet_v2

logger = logging.getLogger(__name__)


_HOME_READINESS_STRUCTURED_DOMAINS = (
    ("technical", "technicals"),
    ("fundamentals", "fundamentals"),
    ("news", "sentiment_analysis"),
    ("catalyst", "catalyst"),
)
_HOME_READINESS_RUNTIME_DOMAINS = {
    "market": ("technical",),
    "technical": ("technical",),
    "technicals": ("technical",),
    "fundamentals": ("fundamentals",),
    "news": ("news", "catalyst"),
    "sentiment": ("news",),
}
_READINESS_MISSING_STATUSES = {"missing", "failed", "unavailable", "not_configured", "skipped", "error"}
_READINESS_FALLBACK_STATUSES = {"partial", "fallback", "stale", "configured_not_used", "used_unrecorded"}
_EVIDENCE_FRAME_DOMAIN_ORDER = (
    "priceHistory",
    "technicals",
    "fundamentals",
    "earnings",
    "news",
    "catalysts",
    "sentiment",
    "valuation",
    "liquidityContext",
    "macroContext",
)
_EVIDENCE_FRAME_SOURCE_AUTHORITY = {
    True: "scoreGradeAllowed",
    False: "observationOnly",
}
_EVIDENCE_FRAME_DEGRADED_STATUSES = {
    "partial",
    "weak",
    "stale",
    "fallback",
    "configured_not_used",
    "used_unrecorded",
    "insufficient_history",
    "data_unavailable",
}
_EVIDENCE_FRAME_WAITING_STATUSES = {"pending", "waiting", "queued", "loading", "scheduled", "in_progress"}
_EVIDENCE_FRAME_TIMEOUT_TOKENS = ("timeout", "timed out", "deadline", "expired")
_EVIDENCE_FRAME_NEXT_EVIDENCE = {
    "priceHistory": "补充价格历史证据",
    "technicals": "补充技术面证据",
    "fundamentals": "补充基本面证据",
    "earnings": "补充财报证据",
    "news": "补充新闻证据",
    "catalysts": "补充催化剂证据",
    "sentiment": "补充情绪证据",
    "valuation": "补充估值证据",
    "liquidityContext": "补充流动性背景证据",
    "macroContext": "补充宏观背景证据",
}


def _first_present(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _nested_get(payload: Any, *path: str) -> Any:
    current = payload
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _extract_data_quality_report(result: Any) -> Optional[Dict[str, Any]]:
    runtime = getattr(result, "runtime_execution", None)
    if isinstance(runtime, dict) and isinstance(runtime.get("data_quality_report"), dict):
        return runtime["data_quality_report"]
    dashboard = getattr(result, "dashboard", None)
    if isinstance(dashboard, dict):
        structured = dashboard.get("structured_analysis")
        if isinstance(structured, dict) and isinstance(structured.get("data_quality_report"), dict):
            return structured["data_quality_report"]
    return None


def _iter_values(value: Any) -> Iterable[Any]:
    if isinstance(value, (list, tuple, set)):
        return value
    if value is None:
        return ()
    return (value,)


def _readiness_cap_fraction(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if number > 1:
        number = number / 100
    return max(0.0, min(1.0, number))


def _readiness_domains_from_value(value: Any) -> List[str]:
    text = str(value or "").strip()
    if not text:
        return []
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", text).strip("_").lower()
    domains: List[str] = []

    def _append(domain: str) -> None:
        if domain not in domains:
            domains.append(domain)

    if normalized in {"price_ohlcv", "technical_history"} or "technical" in normalized or "ohlcv" in normalized:
        _append("technical")
    if "fundamental" in normalized or "financial" in normalized or "earnings" in normalized:
        _append("fundamentals")
    if "news" in normalized or "sentiment" in normalized:
        _append("news")
    if "catalyst" in normalized or normalized.endswith("_event") or normalized == "event":
        _append("catalyst")
    if normalized in {"macro", "market", "market_sector_context", "regime"} or "macro" in normalized:
        _append("macro")
    if "liquidity" in normalized or normalized == "flow":
        _append("liquidity")
    return domains


def _append_readiness_domains(domains: List[str], value: Any) -> None:
    for item in _iter_values(value):
        for domain in _readiness_domains_from_value(item):
            if domain not in domains:
                domains.append(domain)


def _block_status(value: Dict[str, Any]) -> str:
    return str(value.get("status") or value.get("state") or "").strip().lower()


def _analysis_readiness_evidence_item(domain: str, block: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    source = _first_present(
        block.get("source"),
        block.get("provider"),
        block.get("providerId"),
        block.get("providerName"),
    )
    status = _block_status(block)
    if not source and status in _READINESS_MISSING_STATUSES:
        return None
    if not source and not any(
        key in block
        for key in (
            "sourceType",
            "sourceTier",
            "trustLevel",
            "freshness",
            "sourceAuthorityAllowed",
            "scoreContributionAllowed",
        )
    ):
        return None

    freshness = _first_present(block.get("freshness"), block.get("freshnessClass"))
    if not freshness:
        if status == "stale":
            freshness = "stale"
        elif status in {"partial", "fallback", "configured_not_used", "used_unrecorded"}:
            freshness = "delayed"
    item: Dict[str, Any] = {
        "domain": domain,
        "source": source or f"{domain}_metadata",
        "freshness": freshness or "unknown",
    }
    for key in (
        "sourceType",
        "sourceTier",
        "trustLevel",
        "sourceAuthorityAllowed",
        "scoreContributionAllowed",
        "observationOnly",
        "proxyOnly",
        "isFallback",
        "isStale",
        "isSynthetic",
        "isUnavailable",
    ):
        if key in block:
            item[key] = block[key]
    if "sourceTier" not in item and block.get("source_type"):
        item["sourceTier"] = block.get("source_type")
    if "sourceType" not in item and block.get("source_type"):
        item["sourceType"] = block.get("source_type")
    if status in _READINESS_FALLBACK_STATUSES:
        item.setdefault("observationOnly", True)
    if status in _READINESS_MISSING_STATUSES:
        item["isUnavailable"] = True
        item.setdefault("observationOnly", True)
        item.setdefault("sourceAuthorityAllowed", False)
        item.setdefault("scoreContributionAllowed", False)
    cap = _readiness_cap_fraction(block.get("scoreCap"))
    if cap is not None:
        item["scoreCap"] = cap
    return item


def _home_research_readiness_missing_domains(data_quality_report: Optional[Dict[str, Any]]) -> List[str]:
    missing: List[str] = []
    if not isinstance(data_quality_report, dict):
        return missing
    for key in (
        "missingRequiredDomains",
        "importantDomainsMissing",
        "optionalMissing",
        "importantMissing",
        "missingDomains",
        "missingEvidence",
    ):
        _append_readiness_domains(missing, data_quality_report.get(key))
    if data_quality_report.get("requiredAvailable") is False:
        _append_readiness_domains(missing, data_quality_report.get("missingRequiredDomains") or "technical")
    return missing


def _home_research_readiness_freshness(data_quality_report: Optional[Dict[str, Any]]) -> Optional[str]:
    if not isinstance(data_quality_report, dict):
        return None
    reason_codes = {str(item or "").strip().lower() for item in data_quality_report.get("reasonCodes") or []}
    if any("synthetic" in item or "mock" in item for item in reason_codes):
        return "synthetic"
    if any("fallback" in item or "non_live" in item for item in reason_codes):
        return "fallback"
    if data_quality_report.get("staleSources") or "stale_required_source" in reason_codes:
        return "stale"
    return None


def _sentiment_label_for_score(
    score: Any,
    report_language: str,
    data_quality_report: Optional[Dict[str, Any]],
) -> Optional[str]:
    if score is None:
        if isinstance(data_quality_report, dict) and data_quality_report.get("scoreSuppressed"):
            return "Data insufficient" if report_language == "en" else "数据不足"
        return None
    return get_sentiment_label(score, report_language)


def _score_state_from_quality(score: Any, data_quality_report: Optional[Dict[str, Any]]) -> str:
    if isinstance(data_quality_report, dict) and data_quality_report.get("scoreSuppressed"):
        return "suppressed"
    if score is None:
        return "unavailable"
    if isinstance(data_quality_report, dict):
        cap = data_quality_report.get("confidenceCap")
        try:
            cap_value = int(cap)
        except (TypeError, ValueError):
            cap_value = 100
        if cap_value < 100:
            return "capped"
    return "scored"


def _runtime_field(value: Any) -> Dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _runtime_field_status(value: Any) -> str:
    field = _runtime_field(value)
    status = str(field.get("status") or "").strip().lower()
    if status in _EVIDENCE_FRAME_WAITING_STATUSES:
        return "pending"
    if status in {"failed", "error"}:
        return "failed"
    if status in {"missing", "unavailable", "not_configured", "skipped"}:
        return "missing"
    if status in _EVIDENCE_FRAME_DEGRADED_STATUSES:
        return "degraded"
    if status == "ok":
        return "ok"
    return status or "unknown"


def _runtime_field_timeout(value: Any) -> bool:
    field = _runtime_field(value)
    text = " ".join(
        str(field.get(key) or "").strip().lower()
        for key in ("final_reason", "reason", "message", "note")
    )
    return any(token in text for token in _EVIDENCE_FRAME_TIMEOUT_TOKENS)


def _normalize_freshness_value(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"fresh", "live", "realtime", "real_time"}:
        return "fresh"
    if text in {"delayed", "partial", "cached"}:
        return "delayed"
    if text == "stale":
        return "stale"
    if text in {"fallback", "proxy"}:
        return "fallback"
    if text in {"synthetic", "mock"}:
        return "synthetic"
    return "unknown"


def _coverage_freshness(*values: Any) -> str:
    for value in values:
        if isinstance(value, dict):
            normalized = _normalize_freshness_value(
                _first_present(
                    value.get("freshness"),
                    value.get("freshnessClass"),
                    value.get("freshness_floor"),
                )
            )
            if normalized != "unknown":
                return normalized
            if _runtime_field_status(value) == "degraded":
                return "delayed"
        else:
            normalized = _normalize_freshness_value(value)
            if normalized != "unknown":
                return normalized
    return "unknown"


def _coverage_fallback_or_proxy(*values: Any) -> bool:
    for value in values:
        if not isinstance(value, dict):
            text = str(value or "").strip().lower()
            if text and ("proxy" in text or "fallback" in text):
                return True
            continue
        if any(
            value.get(key)
            for key in ("proxyOnly", "isFallback", "fallback_occurred", "fallbackUsed", "proxy_only")
        ):
            return True
        text = " ".join(
            str(value.get(key) or "").strip().lower()
            for key in ("source", "sourceType", "sourceTier", "status")
        )
        if "proxy" in text or "fallback" in text:
            return True
    return False


def _coverage_source_tier(*values: Any) -> Optional[str]:
    for value in values:
        if not isinstance(value, dict):
            continue
        source_tier = _first_present(value.get("sourceTier"), value.get("sourceType"))
        if source_tier is not None:
            return str(source_tier)
    return None


def _coverage_source_authority(*values: Any) -> str:
    saw_metadata = False
    for value in values:
        if not isinstance(value, dict):
            continue
        if any(
            key in value
            for key in ("sourceAuthorityAllowed", "scoreContributionAllowed", "sourceTier", "sourceType", "source")
        ):
            saw_metadata = True
        if (
            value.get("sourceAuthorityAllowed") is True
            and value.get("scoreContributionAllowed") is True
            and not _coverage_fallback_or_proxy(value)
            and _coverage_freshness(value) == "fresh"
        ):
            return _EVIDENCE_FRAME_SOURCE_AUTHORITY[True]
    if saw_metadata:
        return _EVIDENCE_FRAME_SOURCE_AUTHORITY[False]
    return "unavailable"


def _coverage_missing_reasons(
    *,
    structured_status: str,
    runtime_status: str,
    freshness: str,
    fallback_or_proxy: bool,
    missing_fields: Optional[Iterable[Any]] = None,
    partial_flags: Optional[Iterable[Any]] = None,
    coverage_assembled: bool = True,
    weak_relevance: bool = False,
    timeout: bool = False,
) -> List[str]:
    reasons: List[str] = []
    if timeout:
        reasons.append("provider_timeout")
    elif runtime_status == "failed":
        reasons.append("provider_unavailable")
    if structured_status in {"missing", "failed"}:
        reasons.append("evidence_missing")
    if structured_status in _EVIDENCE_FRAME_WAITING_STATUSES or runtime_status == "pending":
        reasons.append("evidence_pending")
    if structured_status in _EVIDENCE_FRAME_DEGRADED_STATUSES or runtime_status == "degraded":
        reasons.append("partial_coverage")
    if freshness in {"delayed", "stale"}:
        reasons.append("stale_evidence")
    if freshness == "fallback" or fallback_or_proxy:
        reasons.append("fallback_proxy_evidence")
    if weak_relevance:
        reasons.append("weak_relevance")
    if any(_iter_values(missing_fields)):
        reasons.append("missing_required_fields")
    if any(_iter_values(partial_flags)):
        reasons.append("partial_coverage")
    if not coverage_assembled:
        reasons.append("coverage_not_assembled")
    return list(dict.fromkeys(reasons))


def _coverage_next_needed(domain: str, status: str) -> List[str]:
    if status in {"available", "not_applicable"}:
        return []
    return [_EVIDENCE_FRAME_NEXT_EVIDENCE[domain]]


def _coverage_frame_entry(
    *,
    domain: str,
    status: str,
    source_tier: Optional[str],
    source_authority: str,
    freshness: str,
    fallback_or_proxy: bool,
    missing_reasons: List[str],
) -> Dict[str, Any]:
    return {
        "status": status,
        "sourceTier": source_tier,
        "sourceAuthority": source_authority,
        "freshness": freshness,
        "fallbackOrProxy": bool(fallback_or_proxy),
        "missingReasons": missing_reasons,
        "nextEvidenceNeeded": _coverage_next_needed(domain, status),
    }


def _coverage_status_from_signals(
    *,
    has_evidence: bool,
    structured_status: str,
    runtime_status: str,
    freshness: str,
    fallback_or_proxy: bool,
    timeout: bool = False,
    missing_reasons: Optional[List[str]] = None,
) -> str:
    reasons = missing_reasons or []
    if structured_status in _EVIDENCE_FRAME_WAITING_STATUSES or runtime_status == "pending":
        return "pending"
    if timeout or runtime_status == "failed":
        return "blocked"
    if structured_status in {"missing", "failed"} and runtime_status in {"missing", "unknown", ""}:
        return "missing"
    if not has_evidence:
        return "missing"
    if (
        structured_status in _EVIDENCE_FRAME_DEGRADED_STATUSES
        or runtime_status == "degraded"
        or freshness != "fresh"
        or fallback_or_proxy
        or reasons
    ):
        return "degraded"
    return "available"


def _has_any_metric(mapping: Any, keys: Iterable[str]) -> bool:
    if not isinstance(mapping, dict):
        return False
    for key in keys:
        value = mapping.get(key)
        if value not in (None, "", "N/A"):
            return True
    return False


def _is_ungrounded_level(value: Any) -> bool:
    text = str(value or "").strip().lower()
    return text in {"待补充", "tbd", "data unavailable", "数据不足", "数据缺失"}


def _redact_public_artifact(value: Any) -> Any:
    """Redact raw prompt/provider/debug content before public export."""
    sensitive_key_markers = (
        "raw_prompt",
        "raw_provider_payload",
        "raw_model_response",
        "raw_response",
        "provider_payload",
        "debug_schema",
        "stack_trace",
        "traceback",
        "trace_id",
        "traceid",
        "request_id",
        "session_id",
        "hidden_reasoning",
        "internal_reasoning",
        "chain_of_thought",
    )
    sensitive_value_markers = (
        "api_key",
        "apikey",
        "token",
        "cookie",
        "session",
        "password",
        "secret",
        "dsn",
        "raw prompt",
        "hidden reasoning",
        "internal reasoning",
        "stack trace",
        "traceback",
    )

    if isinstance(value, dict):
        redacted: Dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            lowered_key = key_text.lower()
            if any(marker in lowered_key for marker in sensitive_key_markers):
                redacted[key_text] = "[redacted]"
                continue
            redacted[key_text] = _redact_public_artifact(item)
        return sanitize_metadata(redacted)
    if isinstance(value, list):
        return [_redact_public_artifact(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_public_artifact(item) for item in value)
    if isinstance(value, str):
        lowered = value.lower()
        if any(marker in lowered for marker in sensitive_value_markers):
            return "[redacted]"
        return sanitize_message(value)
    return value


class AnalysisService:
    """
    分析服务
    
    封装股票分析相关的业务逻辑
    """
    
    def analyze_stock(
        self,
        stock_code: str,
        report_type: str = "detailed",
        force_refresh: bool = False,
        query_id: Optional[str] = None,
        send_notification: bool = True,
        progress_callback: Optional[Callable[[str, int, str], None]] = None,
        owner_id: Optional[str] = None,
        guest_bucket_hash: Optional[str] = None,
        persist_history: bool = True,
        research_mode: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """
        执行股票分析
        
        Args:
            stock_code: 股票代码
            report_type: 报告类型 (simple/detailed)
            force_refresh: 是否强制刷新
            query_id: 查询 ID（可选）
            send_notification: 是否发送通知（API 触发默认发送）
            
        Returns:
            分析结果字典，包含:
            - stock_code: 股票代码
            - stock_name: 股票名称
            - report: 分析报告
        """
        try:
            # 导入分析相关模块
            from src.config import get_config
            from src.core.pipeline import StockAnalysisPipeline
            from src.enums import ReportType
            from src.repositories.analysis_repo import AnalysisRepository
            
            # 生成 query_id
            if query_id is None:
                query_id = uuid.uuid4().hex
            
            # 获取配置
            config = get_config()
            
            # 创建分析流水线
            pipeline = StockAnalysisPipeline(
                config=config,
                query_id=query_id,
                query_source="api",
                owner_id=owner_id,
                guest_bucket_hash=guest_bucket_hash,
                persist_history=persist_history,
            )
            
            # 确定报告类型 (API: simple/detailed/full/brief -> ReportType)
            rt = ReportType.from_str(report_type)
            
            # 执行分析
            result = pipeline.process_single_stock(
                code=stock_code,
                skip_analysis=False,
                single_stock_notify=send_notification,
                report_type=rt,
                force_refresh=force_refresh,
                analysis_query_id=query_id,
                progress_callback=progress_callback,
                research_mode=research_mode,
            )
            
            if result is None:
                logger.warning(f"分析股票 {stock_code} 返回空结果")
                return None
            
            # 构建响应
            response = self._build_analysis_response(result, query_id, report_type=rt.value)
            if persist_history:
                resolved_query_id = str(response.get("query_id") or query_id or "")
                report_payload = response.get("report")
                if resolved_query_id and isinstance(report_payload, dict):
                    saved = AnalysisRepository(owner_id=owner_id).attach_persisted_report(
                        resolved_query_id,
                        report_payload,
                    )
                    if saved <= 0:
                        logger.warning("附加持久化报告失败: query_id=%s stock_code=%s", resolved_query_id, stock_code)
            return response
            
        except Exception as e:
            logger.error(f"分析股票 {stock_code} 失败: {e}", exc_info=True)
            return None
    
    def _build_report_payload(
        self,
        result: Any,
        *,
        query_id: str,
        report_type: str,
    ) -> Dict[str, Any]:
        """Build the canonical report payload from an AnalysisResult."""
        generated_at = to_beijing_iso8601(datetime.utcnow())
        sniper_points = {}
        if hasattr(result, "get_sniper_points"):
            sniper_points = result.get_sniper_points() or {}

        report_language = normalize_report_language(getattr(result, "report_language", "zh"))
        data_quality_report = _extract_data_quality_report(result)
        sentiment_label = _sentiment_label_for_score(result.sentiment_score, report_language, data_quality_report)
        stock_name = get_localized_stock_name(getattr(result, "name", None), result.code, report_language)
        dashboard = getattr(result, "dashboard", None) if isinstance(getattr(result, "dashboard", None), dict) else {}
        structured_analysis = (
            dashboard.get("structured_analysis")
            if isinstance(dashboard.get("structured_analysis"), dict)
            else {}
        )
        runtime = (
            getattr(result, "runtime_execution", None)
            if isinstance(getattr(result, "runtime_execution", None), dict)
            else {}
        )
        runtime_data = runtime.get("data") if isinstance(runtime.get("data"), dict) else {}
        decision_panel = _nested_get(dashboard, "battle_plan", "sniper_points") or {}
        trend_status = _nested_get(dashboard, "data_perspective", "trend_status") or {}
        technical_indicators = _nested_get(dashboard, "data_perspective", "technical_indicators") or {}
        volume_block = _nested_get(dashboard, "data_perspective", "volume_analysis") or {}
        risk_reward = _first_present(
            _nested_get(dashboard, "battle_plan", "risk_reward"),
            _nested_get(dashboard, "battle_plan", "盈亏比"),
        )
        try:
            from src.services.report_renderer import build_standard_report_payload

            standard_report = build_standard_report_payload(result, report_language=report_language)
        except Exception as exc:
            logger.warning("构建 standard_report 失败，降级返回基础详情: %s", exc)
            standard_report = None

        analysis_result = {
            "decision": getattr(result, "decision_type", None),
            "action": getattr(result, "operation_advice", None),
            "score": getattr(result, "sentiment_score", None),
            "score_state": _score_state_from_quality(getattr(result, "sentiment_score", None), data_quality_report),
            "score_suppressed_reason": (
                data_quality_report.get("scoreSuppressedReason") if isinstance(data_quality_report, dict) else None
            ),
            "missing_required_domains": (
                data_quality_report.get("missingRequiredDomains") if isinstance(data_quality_report, dict) else None
            ),
            "confidence_cap": (
                data_quality_report.get("confidenceCap") if isinstance(data_quality_report, dict) else None
            ),
            "confidence": getattr(result, "confidence_level", None),
            "strategy": getattr(result, "trend_prediction", None),
            "entry_price": _first_present(
                sniper_points.get("ideal_buy"),
                decision_panel.get("ideal_buy"),
            ),
            "secondary_entry_price": _first_present(
                sniper_points.get("secondary_buy"),
                decision_panel.get("secondary_buy"),
            ),
            "stop_loss": _first_present(
                sniper_points.get("stop_loss"),
                decision_panel.get("stop_loss"),
            ),
            "take_profit": _first_present(
                sniper_points.get("take_profit"),
                decision_panel.get("take_profit"),
            ),
            "technical_analysis": getattr(result, "technical_analysis", None),
            "ma_alignment": _first_present(
                trend_status.get("ma_alignment"),
                getattr(result, "ma_analysis", None),
            ),
            "rsi": _first_present(
                technical_indicators.get("rsi_14"),
                technical_indicators.get("rsi"),
            ),
            "macd": _first_present(
                technical_indicators.get("macd"),
                getattr(result, "technical_analysis", None),
            ),
            "volume_dynamics": _first_present(
                volume_block.get("volume_meaning"),
                getattr(result, "volume_analysis", None),
            ),
            "risk_reward": risk_reward,
            "full_reasoning": getattr(result, "analysis_summary", None),
            "summary": getattr(result, "analysis_summary", None),
        }
        research_readiness = self._build_home_research_readiness(
            result,
            data_quality_report=data_quality_report,
            structured_analysis=structured_analysis,
            query_id=query_id,
        )
        evidence_coverage_frame = self._build_home_evidence_coverage_frame(
            result,
            data_quality_report=data_quality_report,
            structured_analysis=structured_analysis,
        )
        single_stock_evidence_packet = self._build_home_single_stock_evidence_packet(
            result,
            data_quality_report=data_quality_report,
            structured_analysis=structured_analysis,
            query_id=query_id,
        )
        evidence_citation_frame = self._build_home_report_evidence_citation_frame(
            result,
            research_readiness=research_readiness,
            evidence_coverage_frame=evidence_coverage_frame,
            single_stock_evidence_packet=single_stock_evidence_packet,
            query_id=query_id,
        )
        source_provenance_frame = self._build_home_source_provenance_frame(
            research_readiness=research_readiness,
            evidence_coverage_frame=evidence_coverage_frame,
            single_stock_evidence_packet=single_stock_evidence_packet,
            evidence_citation_frame=evidence_citation_frame,
            source_metadata_by_domain=self._build_home_source_metadata_by_domain(
                structured_analysis=structured_analysis,
                runtime_data=runtime_data,
            ),
            query_id=query_id,
        )
        intelligence_packet = build_intelligence_report_packet_v2(
            {
                "symbol": getattr(result, "code", None),
                "market": self._market_from_symbol(getattr(result, "code", "")).lower(),
                "standardReport": standard_report or {},
                "researchReadiness": research_readiness,
                "evidenceCoverageFrame": evidence_coverage_frame,
                "singleStockEvidencePacket": single_stock_evidence_packet,
                "evidenceCitationFrame": evidence_citation_frame,
                "sourceProvenanceFrame": source_provenance_frame,
                "dataQualityReport": data_quality_report or {},
                "debugRef": f"analysis:{query_id}",
            }
        )
        if isinstance(standard_report, dict):
            standard_report["intelligencePacket"] = intelligence_packet
        analysis_result["researchReadiness"] = research_readiness
        analysis_result["evidenceCoverageFrame"] = evidence_coverage_frame
        analysis_result["singleStockEvidencePacket"] = single_stock_evidence_packet
        analysis_result["evidenceCitationFrame"] = evidence_citation_frame
        analysis_result["sourceProvenanceFrame"] = source_provenance_frame
        analysis_result["intelligencePacket"] = intelligence_packet
        decision_trace = self._build_decision_trace(
            result,
            query_id=query_id,
            report_type=report_type,
        )

        payload = {
            "meta": {
                "query_id": query_id,
                "stock_code": result.code,
                "stock_name": stock_name,
                "company_name": stock_name,
                "report_type": report_type,
                "report_language": report_language,
                "report_generated_at": generated_at,
                "generated_at": generated_at,
                "is_test": False,
                "current_price": result.current_price,
                "change_pct": result.change_pct,
                "model_used": getattr(result, "model_used", None),
                "strategy_type": getattr(result, "decision_type", None) or report_type,
                "evidenceCoverageFrame": evidence_coverage_frame,
                "singleStockEvidencePacket": single_stock_evidence_packet,
                "evidenceCitationFrame": evidence_citation_frame,
                "sourceProvenanceFrame": source_provenance_frame,
                "intelligencePacket": intelligence_packet,
            },
            "summary": {
                "analysis_summary": result.analysis_summary,
                "strategy_summary": result.analysis_summary,
                "operation_advice": localize_operation_advice(result.operation_advice, report_language),
                "trend_prediction": localize_trend_prediction(result.trend_prediction, report_language),
                "sentiment_score": result.sentiment_score,
                "sentiment_label": sentiment_label,
                "score_state": _score_state_from_quality(result.sentiment_score, data_quality_report),
                "confidence_cap": (
                    data_quality_report.get("confidenceCap") if isinstance(data_quality_report, dict) else None
                ),
            },
            "strategy": {
                "ideal_buy": sniper_points.get("ideal_buy"),
                "secondary_buy": sniper_points.get("secondary_buy"),
                "stop_loss": sniper_points.get("stop_loss"),
                "take_profit": sniper_points.get("take_profit"),
            },
            "details": {
                "news_summary": result.news_summary,
                "technical_analysis": result.technical_analysis,
                "fundamental_analysis": result.fundamental_analysis,
                "risk_warning": result.risk_warning,
                "standard_report": standard_report,
                "analysis_result": analysis_result,
                "raw_ai_response": _redact_public_artifact(getattr(result, "raw_response", None)),
            },
            "decision_trace": decision_trace,
            "researchReadiness": research_readiness,
            "evidenceCoverageFrame": evidence_coverage_frame,
            "singleStockEvidencePacket": single_stock_evidence_packet,
            "evidenceCitationFrame": evidence_citation_frame,
            "sourceProvenanceFrame": source_provenance_frame,
            "intelligencePacket": intelligence_packet,
        }
        payload["meta"]["researchReadiness"] = research_readiness
        payload["meta"]["evidenceCitationFrame"] = evidence_citation_frame
        payload["meta"]["sourceProvenanceFrame"] = source_provenance_frame
        payload["meta"]["intelligencePacket"] = intelligence_packet
        if data_quality_report:
            payload["dataQualityReport"] = data_quality_report
            payload["meta"]["dataQualityReport"] = data_quality_report
            payload["details"]["data_quality_report"] = data_quality_report
            payload["details"]["analysis_result"]["dataQualityReport"] = data_quality_report
        return payload

    def _build_home_research_readiness(
        self,
        result: Any,
        *,
        data_quality_report: Optional[Dict[str, Any]],
        structured_analysis: Dict[str, Any],
        query_id: str,
    ) -> Dict[str, Any]:
        missing_domains = _home_research_readiness_missing_domains(data_quality_report)
        evidence: List[Dict[str, Any]] = []
        required_domains: List[str] = []

        for domain, key in _HOME_READINESS_STRUCTURED_DOMAINS:
            block = structured_analysis.get(key)
            if not isinstance(block, dict):
                continue
            status = _block_status(block)
            if status in _READINESS_MISSING_STATUSES:
                _append_readiness_domains(missing_domains, domain)
            item = _analysis_readiness_evidence_item(domain, block)
            if item:
                evidence.append(item)
                _append_readiness_domains(required_domains, domain)

        runtime = getattr(result, "runtime_execution", None) if isinstance(getattr(result, "runtime_execution", None), dict) else {}
        runtime_data = runtime.get("data") if isinstance(runtime.get("data"), dict) else {}
        for key, field in runtime_data.items():
            if not isinstance(field, dict):
                continue
            for domain in _HOME_READINESS_RUNTIME_DOMAINS.get(str(key), ()):
                status = str(field.get("status") or "").strip().lower()
                if status in _READINESS_MISSING_STATUSES:
                    _append_readiness_domains(missing_domains, domain)
                item = _analysis_readiness_evidence_item(domain, field)
                if item:
                    evidence.append(item)
                    _append_readiness_domains(required_domains, domain)

        for domain in missing_domains:
            _append_readiness_domains(required_domains, domain)

        cap = (
            _readiness_cap_fraction(data_quality_report.get("confidenceCap"))
            if isinstance(data_quality_report, dict)
            else None
        )
        score_state = _score_state_from_quality(getattr(result, "sentiment_score", None), data_quality_report)
        evidence_by_domain = {
            str(item.get("domain"))
            for item in evidence
            if item.get("sourceAuthorityAllowed") is True and item.get("scoreContributionAllowed") is True
        }
        source_authority_allowed = bool(
            required_domains
            and not missing_domains
            and all(domain in evidence_by_domain for domain in required_domains)
        )
        payload: Dict[str, Any] = {
            "requiredEvidence": required_domains,
            "missingEvidence": missing_domains,
            "evidence": evidence,
            "dataQualityReport": data_quality_report or {},
            "sourceAuthorityAllowed": source_authority_allowed,
            "scoreContributionAllowed": source_authority_allowed,
            "scoreState": score_state,
            "noAdviceBoundary": True,
            "consumerActionBoundary": "no_advice",
            "debugRef": f"analysis:{query_id}",
        }
        if cap is not None:
            payload["confidenceCap"] = cap
        freshness = _home_research_readiness_freshness(data_quality_report)
        if freshness:
            payload["freshness"] = freshness
        return build_research_readiness_v1(payload)

    def _build_home_single_stock_evidence_packet(
        self,
        result: Any,
        *,
        data_quality_report: Optional[Dict[str, Any]],
        structured_analysis: Dict[str, Any],
        query_id: str,
    ) -> Dict[str, Any]:
        runtime = (
            getattr(result, "runtime_execution", None)
            if isinstance(getattr(result, "runtime_execution", None), dict)
            else {}
        )
        runtime_data = runtime.get("data") if isinstance(runtime.get("data"), dict) else {}
        packet_payload: Dict[str, Any] = {
            "symbol": getattr(result, "code", None),
            "market": self._market_from_symbol(getattr(result, "code", "")).lower(),
            "debugRef": f"analysis:{query_id}",
            "noAdviceBoundary": True,
            "dataQualityReport": data_quality_report or {},
            "structuredAnalysis": structured_analysis,
            "runtimeData": runtime_data,
        }
        news_context = structured_analysis.get("news_context")
        if isinstance(news_context, str) and news_context.strip():
            packet_payload["news_context"] = news_context

        packet = build_single_stock_evidence_packet_v1(packet_payload)
        packet["fundamentalsEarnings"] = build_single_stock_fundamentals_earnings_normalizer_v1(
            packet_payload
        )
        packet["newsCatalysts"] = build_single_stock_news_catalyst_extractor_v1(packet_payload)
        return packet

    def _build_home_report_evidence_citation_frame(
        self,
        result: Any,
        *,
        research_readiness: Dict[str, Any],
        evidence_coverage_frame: Dict[str, Any],
        single_stock_evidence_packet: Dict[str, Any],
        query_id: str,
    ) -> Dict[str, Any]:
        packet_payload: Dict[str, Any] = {
            "singleStockEvidencePacket": single_stock_evidence_packet,
            "fundamentalsEarnings": single_stock_evidence_packet.get("fundamentalsEarnings"),
            "newsCatalysts": single_stock_evidence_packet.get("newsCatalysts"),
            "researchReadiness": research_readiness,
            "evidenceCoverageFrame": evidence_coverage_frame,
            "debugRef": f"analysis:{query_id}",
        }
        home_llm_evidence_input = build_home_llm_evidence_input_v1(packet_payload)
        packet_payload["homeLlmEvidenceInput"] = home_llm_evidence_input
        return build_home_report_evidence_citation_frame_v1(packet_payload)

    def _build_home_source_provenance_frame(
        self,
        *,
        research_readiness: Dict[str, Any],
        evidence_coverage_frame: Dict[str, Any],
        single_stock_evidence_packet: Dict[str, Any],
        evidence_citation_frame: Dict[str, Any],
        source_metadata_by_domain: Dict[str, Dict[str, Any]],
        query_id: str,
    ) -> List[Dict[str, Any]]:
        return build_home_source_provenance_sidecar_v1(
            {
                "singleStockEvidencePacket": single_stock_evidence_packet,
                "evidenceCitationFrame": evidence_citation_frame,
                "evidenceCoverageFrame": evidence_coverage_frame,
                "researchReadiness": research_readiness,
                "sourceMetadataByDomain": source_metadata_by_domain,
                "debugRef": f"analysis:{query_id}",
            }
        )

    @staticmethod
    def _build_home_source_metadata_by_domain(
        *,
        structured_analysis: Dict[str, Any],
        runtime_data: Dict[str, Any],
    ) -> Dict[str, Dict[str, Any]]:
        market_runtime = _runtime_field(
            _first_present(
                runtime_data.get("market"),
                runtime_data.get("quote"),
                runtime_data.get("technical"),
                runtime_data.get("technicals"),
            )
        )
        source_blocks = {
            "priceHistory": (
                market_runtime,
                _runtime_field(structured_analysis.get("realtime_context")),
                _runtime_field(structured_analysis.get("technicals")),
            ),
            "technicals": (
                _runtime_field(structured_analysis.get("technicals")),
                market_runtime,
                _runtime_field(structured_analysis.get("realtime_context")),
            ),
            "fundamentals": (
                _runtime_field(structured_analysis.get("fundamentals")),
                _runtime_field(runtime_data.get("fundamentals")),
            ),
            "earnings": (
                _runtime_field(structured_analysis.get("earnings_analysis")),
                _runtime_field(structured_analysis.get("fundamentals")),
                _runtime_field(runtime_data.get("fundamentals")),
            ),
            "filings": (
                _runtime_field(structured_analysis.get("filings")),
            ),
            "news": (
                _runtime_field(structured_analysis.get("sentiment_analysis")),
                _runtime_field(runtime_data.get("news")),
            ),
            "catalysts": (
                _runtime_field(structured_analysis.get("catalyst")),
                _runtime_field(structured_analysis.get("sentiment_analysis")),
                _runtime_field(runtime_data.get("news")),
            ),
            "sentiment": (
                _runtime_field(structured_analysis.get("sentiment_analysis")),
                _runtime_field(runtime_data.get("sentiment")),
            ),
            "valuation": (
                _runtime_field(structured_analysis.get("fundamentals")),
                _runtime_field(runtime_data.get("fundamentals")),
            ),
            "sectorTheme": (
                _runtime_field(structured_analysis.get("market_context")),
            ),
            "macroLiquidity": (
                _runtime_field(structured_analysis.get("market_context")),
            ),
        }
        return {
            domain: metadata
            for domain, blocks in source_blocks.items()
            if (metadata := AnalysisService._source_metadata_from_blocks(blocks))
        }

    @staticmethod
    def _source_metadata_from_blocks(blocks: Iterable[Dict[str, Any]]) -> Dict[str, Any]:
        normalized_blocks = [block for block in blocks if isinstance(block, dict) and block]
        source_id = _first_present(
            *(
                _first_present(
                    block.get("sourceId"),
                    block.get("source_id"),
                    block.get("source"),
                    _nested_get(block, "field_sources", "quarterly_series"),
                )
                for block in normalized_blocks
            )
        )
        if source_id is None:
            return {}
        source_tier = _coverage_source_tier(*normalized_blocks)
        authority = _first_present(
            *(
                _first_present(
                    block.get("providerAuthority"),
                    block.get("sourceAuthority"),
                    block.get("trustLevel"),
                )
                for block in normalized_blocks
            )
        )
        if authority is None:
            authority = _coverage_source_authority(*normalized_blocks)
        if authority == "unavailable" and any(block.get("scoreContributionAllowed") is True for block in normalized_blocks):
            authority = "scoreGradeAllowed"
        freshness = _coverage_freshness(*normalized_blocks)
        fallback_or_proxy = _coverage_fallback_or_proxy(*normalized_blocks)
        score_allowed = any(block.get("scoreContributionAllowed") is True for block in normalized_blocks)
        if authority == "scoreGradeAllowed" and freshness in {"fresh", "cached"} and not fallback_or_proxy:
            score_allowed = True
        return {
            "sourceId": source_id,
            "sourceLabel": _first_present(
                *(
                    _first_present(
                        block.get("sourceLabel"),
                        block.get("source_label"),
                        block.get("label"),
                        block.get("source"),
                    )
                    for block in normalized_blocks
                )
            ),
            "sourceTier": source_tier,
            "providerAuthority": authority,
            "freshness": freshness,
            "fallbackOrProxy": fallback_or_proxy,
            "observationOnly": authority != "scoreGradeAllowed",
            "scoreContributionAllowed": score_allowed,
        }

    def _build_home_evidence_coverage_frame(
        self,
        result: Any,
        *,
        data_quality_report: Optional[Dict[str, Any]],
        structured_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:
        runtime = getattr(result, "runtime_execution", None) if isinstance(getattr(result, "runtime_execution", None), dict) else {}
        runtime_data = runtime.get("data") if isinstance(runtime.get("data"), dict) else {}
        quality = data_quality_report if isinstance(data_quality_report, dict) else {}

        technicals = structured_analysis.get("technicals") if isinstance(structured_analysis.get("technicals"), dict) else {}
        fundamentals = structured_analysis.get("fundamentals") if isinstance(structured_analysis.get("fundamentals"), dict) else {}
        earnings = structured_analysis.get("earnings_analysis") if isinstance(structured_analysis.get("earnings_analysis"), dict) else {}
        sentiment = structured_analysis.get("sentiment_analysis") if isinstance(structured_analysis.get("sentiment_analysis"), dict) else {}
        catalyst = structured_analysis.get("catalyst") if isinstance(structured_analysis.get("catalyst"), dict) else {}
        realtime_context = structured_analysis.get("realtime_context") if isinstance(structured_analysis.get("realtime_context"), dict) else {}
        market_context = structured_analysis.get("market_context") if isinstance(structured_analysis.get("market_context"), dict) else {}

        runtime_market = _runtime_field(runtime_data.get("market"))
        runtime_fundamentals = _runtime_field(runtime_data.get("fundamentals"))
        runtime_news = _runtime_field(runtime_data.get("news"))
        runtime_sentiment = _runtime_field(runtime_data.get("sentiment"))

        frame: Dict[str, Any] = {}

        price_history_missing_fields = [
            item for item in (quality.get("missingRequiredDomains") or [])
            if "price" in str(item).lower() or "ohlcv" in str(item).lower() or "technical_history" in str(item).lower()
        ]
        price_history_structured_status = str(quality.get("price_history_status") or _block_status(technicals) or "").strip().lower()
        price_history_runtime_status = _runtime_field_status(runtime_market)
        price_history_freshness = _coverage_freshness(technicals, runtime_market, realtime_context)
        price_history_fallback = _coverage_fallback_or_proxy(technicals, runtime_market, realtime_context)
        price_history_has_evidence = bool(technicals or runtime_market or realtime_context)
        price_history_reasons = _coverage_missing_reasons(
            structured_status=price_history_structured_status,
            runtime_status=price_history_runtime_status,
            freshness=price_history_freshness,
            fallback_or_proxy=price_history_fallback,
            missing_fields=price_history_missing_fields,
        )
        frame["priceHistory"] = _coverage_frame_entry(
            domain="priceHistory",
            status=_coverage_status_from_signals(
                has_evidence=price_history_has_evidence,
                structured_status=price_history_structured_status,
                runtime_status=price_history_runtime_status,
                freshness=price_history_freshness,
                fallback_or_proxy=price_history_fallback,
                missing_reasons=price_history_reasons,
            ),
            source_tier=_coverage_source_tier(technicals, runtime_market),
            source_authority=_coverage_source_authority(technicals, runtime_market),
            freshness=price_history_freshness,
            fallback_or_proxy=price_history_fallback,
            missing_reasons=price_history_reasons,
        )

        technical_status = str(quality.get("technicals_status") or _block_status(technicals) or "").strip().lower()
        technical_freshness = _coverage_freshness(technicals)
        technical_fallback = _coverage_fallback_or_proxy(technicals)
        technical_missing_fields = [item for item in (quality.get("missing_fields") or []) if str(item).startswith("technicals.")]
        technical_reasons = _coverage_missing_reasons(
            structured_status=technical_status,
            runtime_status="unknown",
            freshness=technical_freshness,
            fallback_or_proxy=technical_fallback,
            missing_fields=technical_missing_fields,
        )
        frame["technicals"] = _coverage_frame_entry(
            domain="technicals",
            status=_coverage_status_from_signals(
                has_evidence=bool(technicals),
                structured_status=technical_status,
                runtime_status="unknown",
                freshness=technical_freshness,
                fallback_or_proxy=technical_fallback,
                missing_reasons=technical_reasons,
            ),
            source_tier=_coverage_source_tier(technicals),
            source_authority=_coverage_source_authority(technicals),
            freshness=technical_freshness,
            fallback_or_proxy=technical_fallback,
            missing_reasons=technical_reasons,
        )

        fundamentals_status = str(quality.get("fundamentals_status") or _block_status(fundamentals) or "").strip().lower()
        fundamentals_runtime_status = _runtime_field_status(runtime_fundamentals)
        fundamentals_freshness = _coverage_freshness(fundamentals, runtime_fundamentals)
        fundamentals_fallback = _coverage_fallback_or_proxy(fundamentals, runtime_fundamentals)
        fundamentals_reasons = _coverage_missing_reasons(
            structured_status=fundamentals_status,
            runtime_status=fundamentals_runtime_status,
            freshness=fundamentals_freshness,
            fallback_or_proxy=fundamentals_fallback,
            missing_fields=fundamentals.get("missing_fields"),
            timeout=_runtime_field_timeout(runtime_fundamentals),
        )
        frame["fundamentals"] = _coverage_frame_entry(
            domain="fundamentals",
            status=_coverage_status_from_signals(
                has_evidence=bool(fundamentals),
                structured_status=fundamentals_status,
                runtime_status=fundamentals_runtime_status,
                freshness=fundamentals_freshness,
                fallback_or_proxy=fundamentals_fallback,
                timeout=_runtime_field_timeout(runtime_fundamentals),
                missing_reasons=fundamentals_reasons,
            ),
            source_tier=_coverage_source_tier(fundamentals, runtime_fundamentals),
            source_authority=_coverage_source_authority(fundamentals, runtime_fundamentals),
            freshness=fundamentals_freshness,
            fallback_or_proxy=fundamentals_fallback,
            missing_reasons=fundamentals_reasons,
        )

        earnings_status = str(quality.get("earnings_status") or _block_status(earnings) or "").strip().lower()
        earnings_freshness = _coverage_freshness(earnings)
        earnings_partial_flags = [
            item for item in (earnings.get("summary_flags") or [])
            if any(token in str(item).lower() for token in ("partial", "unavailable", "missing"))
        ]
        earnings_reasons = _coverage_missing_reasons(
            structured_status=earnings_status,
            runtime_status="unknown",
            freshness=earnings_freshness,
            fallback_or_proxy=False,
            partial_flags=earnings_partial_flags,
        )
        frame["earnings"] = _coverage_frame_entry(
            domain="earnings",
            status=_coverage_status_from_signals(
                has_evidence=bool(earnings),
                structured_status=earnings_status,
                runtime_status="unknown",
                freshness=earnings_freshness,
                fallback_or_proxy=False,
                missing_reasons=earnings_reasons,
            ),
            source_tier=_coverage_source_tier(earnings),
            source_authority=_coverage_source_authority(earnings),
            freshness=earnings_freshness,
            fallback_or_proxy=False,
            missing_reasons=earnings_reasons,
        )

        news_structured_status = str(_block_status(sentiment) or "").strip().lower()
        news_runtime_status = _runtime_field_status(runtime_news)
        news_freshness = _coverage_freshness(sentiment, runtime_news)
        news_fallback = _coverage_fallback_or_proxy(sentiment, runtime_news)
        weak_relevance = str(sentiment.get("relevance_type") or "").strip().lower() == "low_relevance"
        news_reasons = _coverage_missing_reasons(
            structured_status=news_structured_status,
            runtime_status=news_runtime_status,
            freshness=news_freshness,
            fallback_or_proxy=news_fallback,
            weak_relevance=weak_relevance,
            timeout=_runtime_field_timeout(runtime_news),
        )
        frame["news"] = _coverage_frame_entry(
            domain="news",
            status=_coverage_status_from_signals(
                has_evidence=bool(sentiment) or bool(runtime_news),
                structured_status=news_structured_status,
                runtime_status=news_runtime_status,
                freshness=news_freshness,
                fallback_or_proxy=news_fallback,
                timeout=_runtime_field_timeout(runtime_news),
                missing_reasons=news_reasons,
            ),
            source_tier=_coverage_source_tier(sentiment, runtime_news),
            source_authority=_coverage_source_authority(sentiment, runtime_news),
            freshness=news_freshness,
            fallback_or_proxy=news_fallback,
            missing_reasons=news_reasons,
        )

        catalyst_structured_status = str(_block_status(catalyst) or news_structured_status or "").strip().lower()
        catalyst_runtime_status = news_runtime_status
        catalyst_freshness = _coverage_freshness(catalyst, sentiment, runtime_news)
        catalyst_fallback = _coverage_fallback_or_proxy(catalyst, sentiment, runtime_news)
        catalyst_has_evidence = bool(catalyst) or bool(sentiment.get("classified_items"))
        catalyst_reasons = _coverage_missing_reasons(
            structured_status=catalyst_structured_status,
            runtime_status=catalyst_runtime_status,
            freshness=catalyst_freshness,
            fallback_or_proxy=catalyst_fallback,
            weak_relevance=weak_relevance,
            timeout=_runtime_field_timeout(runtime_news),
        )
        frame["catalysts"] = _coverage_frame_entry(
            domain="catalysts",
            status=_coverage_status_from_signals(
                has_evidence=catalyst_has_evidence,
                structured_status=catalyst_structured_status,
                runtime_status=catalyst_runtime_status,
                freshness=catalyst_freshness,
                fallback_or_proxy=catalyst_fallback,
                timeout=_runtime_field_timeout(runtime_news),
                missing_reasons=catalyst_reasons,
            ),
            source_tier=_coverage_source_tier(catalyst, sentiment, runtime_news),
            source_authority=_coverage_source_authority(catalyst, sentiment, runtime_news),
            freshness=catalyst_freshness,
            fallback_or_proxy=catalyst_fallback,
            missing_reasons=catalyst_reasons,
        )

        sentiment_structured_status = str(quality.get("sentiment_status") or _block_status(sentiment) or "").strip().lower()
        sentiment_runtime_status = _runtime_field_status(runtime_sentiment)
        sentiment_freshness = _coverage_freshness(sentiment, runtime_sentiment)
        sentiment_fallback = _coverage_fallback_or_proxy(sentiment, runtime_sentiment)
        sentiment_reasons = _coverage_missing_reasons(
            structured_status=sentiment_structured_status,
            runtime_status=sentiment_runtime_status,
            freshness=sentiment_freshness,
            fallback_or_proxy=sentiment_fallback,
            weak_relevance=weak_relevance,
            timeout=_runtime_field_timeout(runtime_sentiment),
        )
        frame["sentiment"] = _coverage_frame_entry(
            domain="sentiment",
            status=_coverage_status_from_signals(
                has_evidence=bool(sentiment) or bool(runtime_sentiment),
                structured_status=sentiment_structured_status,
                runtime_status=sentiment_runtime_status,
                freshness=sentiment_freshness,
                fallback_or_proxy=sentiment_fallback,
                timeout=_runtime_field_timeout(runtime_sentiment),
                missing_reasons=sentiment_reasons,
            ),
            source_tier=_coverage_source_tier(sentiment, runtime_sentiment),
            source_authority=_coverage_source_authority(sentiment, runtime_sentiment),
            freshness=sentiment_freshness,
            fallback_or_proxy=sentiment_fallback,
            missing_reasons=sentiment_reasons,
        )

        valuation_has_metrics = _has_any_metric(fundamentals.get("normalized"), ("trailingPE", "forwardPE", "priceToBook"))
        valuation_reasons = _coverage_missing_reasons(
            structured_status=fundamentals_status,
            runtime_status=fundamentals_runtime_status,
            freshness=fundamentals_freshness,
            fallback_or_proxy=fundamentals_fallback,
            missing_fields=None if valuation_has_metrics else ["valuation_metrics_missing"],
            timeout=_runtime_field_timeout(runtime_fundamentals),
        )
        frame["valuation"] = _coverage_frame_entry(
            domain="valuation",
            status=_coverage_status_from_signals(
                has_evidence=valuation_has_metrics,
                structured_status=fundamentals_status,
                runtime_status=fundamentals_runtime_status,
                freshness=fundamentals_freshness,
                fallback_or_proxy=fundamentals_fallback,
                timeout=_runtime_field_timeout(runtime_fundamentals),
                missing_reasons=valuation_reasons,
            ),
            source_tier=_coverage_source_tier(fundamentals, runtime_fundamentals),
            source_authority=_coverage_source_authority(fundamentals, runtime_fundamentals),
            freshness=fundamentals_freshness,
            fallback_or_proxy=fundamentals_fallback,
            missing_reasons=valuation_reasons,
        )

        liquidity_has_evidence = any(
            realtime_context.get(key) not in (None, "", "0", 0, "0.0")
            for key in ("volume_ratio", "turnover_rate")
        )
        liquidity_freshness = _coverage_freshness(realtime_context, runtime_market)
        liquidity_fallback = _coverage_fallback_or_proxy(realtime_context, runtime_market)
        liquidity_reasons = _coverage_missing_reasons(
            structured_status="ok" if liquidity_has_evidence else "missing",
            runtime_status="unknown",
            freshness=liquidity_freshness,
            fallback_or_proxy=liquidity_fallback,
            missing_fields=None if liquidity_has_evidence else ["liquidity_metrics_missing"],
        )
        frame["liquidityContext"] = _coverage_frame_entry(
            domain="liquidityContext",
            status=_coverage_status_from_signals(
                has_evidence=liquidity_has_evidence,
                structured_status="ok" if liquidity_has_evidence else "missing",
                runtime_status="unknown",
                freshness=liquidity_freshness,
                fallback_or_proxy=liquidity_fallback,
                missing_reasons=liquidity_reasons,
            ),
            source_tier=_coverage_source_tier(realtime_context, runtime_market),
            source_authority=_coverage_source_authority(realtime_context, runtime_market),
            freshness=liquidity_freshness,
            fallback_or_proxy=liquidity_fallback,
            missing_reasons=liquidity_reasons,
        )

        macro_has_evidence = any(
            key in market_context
            for key in ("macro", "regime", "breadth", "liquidity", "macroContext")
        )
        macro_freshness = _coverage_freshness(market_context)
        macro_fallback = _coverage_fallback_or_proxy(market_context)
        macro_reasons = _coverage_missing_reasons(
            structured_status="ok" if macro_has_evidence else "missing",
            runtime_status="unknown",
            freshness=macro_freshness,
            fallback_or_proxy=macro_fallback,
            coverage_assembled=macro_has_evidence,
        )
        frame["macroContext"] = _coverage_frame_entry(
            domain="macroContext",
            status=_coverage_status_from_signals(
                has_evidence=macro_has_evidence,
                structured_status="ok" if macro_has_evidence else "missing",
                runtime_status="unknown",
                freshness=macro_freshness,
                fallback_or_proxy=macro_fallback,
                missing_reasons=macro_reasons,
            ),
            source_tier=_coverage_source_tier(market_context),
            source_authority=_coverage_source_authority(market_context),
            freshness=macro_freshness,
            fallback_or_proxy=macro_fallback,
            missing_reasons=macro_reasons,
        )

        return {domain: frame[domain] for domain in _EVIDENCE_FRAME_DOMAIN_ORDER}

    @staticmethod
    def _normalize_action(value: Any) -> str:
        text = str(value or "").strip().lower()
        if any(token in text for token in ("data_insufficient", "data insufficient", "数据不足", "禁止判断")):
            return "data_insufficient"
        if any(token in text for token in ("sell", "reduce", "avoid", "卖", "减", "规避", "看空")):
            return "sell"
        if any(token in text for token in ("buy", "add", "accumulate", "买", "加仓", "建仓", "看多")):
            return "buy"
        if any(token in text for token in ("hold", "watch", "wait", "持有", "观望", "等待")):
            return "hold"
        return text or "unknown"

    @staticmethod
    def _confidence_numeric(value: Any) -> Optional[float]:
        if isinstance(value, (int, float)):
            parsed = float(value)
            return max(0.0, min(1.0, parsed / 100 if parsed > 1 else parsed))
        text = str(value or "").strip().lower()
        if text in {"高", "high"}:
            return 0.76
        if text in {"中", "medium"}:
            return 0.56
        if text in {"低", "low"}:
            return 0.34
        return None

    @staticmethod
    def _safe_public_text(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        if not text:
            return None
        lowered = text.lower()
        sensitive_markers = (
            "api_key",
            "apikey",
            "secret",
            "bearer ",
            "sk-",
            "token",
            "cookie",
            "session",
            "password",
            "traceback",
            "stack trace",
            "raw_provider_payload",
            "raw_prompt",
        )
        if any(marker in lowered for marker in sensitive_markers):
            return "[redacted]"
        return text[:160]

    @staticmethod
    def _runtime_data_status(field: Dict[str, Any]) -> str:
        if not field:
            return "unknown"
        if field.get("fallback_occurred"):
            return "fallback"
        status = str(field.get("status") or "").strip().lower()
        truth = str(field.get("truth") or "").strip().lower()
        if status in {"ok", "used", "partial"} or truth == "actual":
            return "used"
        if status in {"failed", "missing", "not_configured", "unavailable"} or truth == "unavailable":
            return "missing"
        if status == "stale":
            return "stale"
        return "unknown"

    @staticmethod
    def _status_from_structured(block: Dict[str, Any]) -> str:
        status = str(block.get("status") or "").strip().lower()
        if status in {"ok", "used"}:
            return "used"
        if status in {"partial", "fallback"}:
            return "fallback"
        if status in {"missing", "failed", "not_configured", "unavailable"}:
            return "missing"
        if status == "stale":
            return "stale"
        return "unknown"

    @staticmethod
    def _market_from_symbol(symbol: str) -> str:
        text = str(symbol or "").strip().upper()
        if text.startswith("HK"):
            return "HK"
        if text.isalpha():
            return "US"
        return "CN" if text else "unknown"

    def _build_decision_trace(
        self,
        result: Any,
        *,
        query_id: str,
        report_type: str,
    ) -> Dict[str, Any]:
        dashboard = getattr(result, "dashboard", None) if isinstance(getattr(result, "dashboard", None), dict) else {}
        structured = dashboard.get("structured_analysis") if isinstance(dashboard.get("structured_analysis"), dict) else {}
        decision_context = dashboard.get("decision_context") if isinstance(dashboard.get("decision_context"), dict) else {}
        battle_plan = dashboard.get("battle_plan") if isinstance(dashboard.get("battle_plan"), dict) else {}
        position_strategy = battle_plan.get("position_strategy") if isinstance(battle_plan.get("position_strategy"), dict) else {}
        sniper_points = result.get_sniper_points() if hasattr(result, "get_sniper_points") else {}
        if not isinstance(sniper_points, dict):
            sniper_points = {}
        data_quality_report = (
            structured.get("data_quality_report")
            if isinstance(structured.get("data_quality_report"), dict)
            else _extract_data_quality_report(result)
        )
        score_suppressed = (
            bool(data_quality_report.get("scoreSuppressed"))
            if isinstance(data_quality_report, dict)
            else False
        )
        key_levels_ungrounded = (
            isinstance(data_quality_report, dict)
            and str(data_quality_report.get("keyLevelGuardrail") or "").strip().lower() == "ungrounded"
        )
        runtime = getattr(result, "runtime_execution", None) if isinstance(getattr(result, "runtime_execution", None), dict) else {}
        runtime_ai = runtime.get("ai") if isinstance(runtime.get("ai"), dict) else {}
        runtime_data = runtime.get("data") if isinstance(runtime.get("data"), dict) else {}
        model_used = self._safe_public_text(runtime_ai.get("model") or getattr(result, "model_used", None))
        provider = self._safe_public_text(runtime_ai.get("provider"))
        if not provider and model_used and "/" in model_used:
            provider = model_used.split("/", 1)[0]
        has_rule_scoring = bool(decision_context.get("score_breakdown"))
        mode = "rule_scoring_with_llm_explanation" if has_rule_scoring else ("llm_direct" if model_used else "unknown")
        action_source = "rule" if has_rule_scoring else ("llm" if model_used else "fallback")
        score_source = "rule" if has_rule_scoring else ("llm" if model_used else "fallback")
        if score_suppressed:
            action_source = "data_quality_guardrail"
            score_source = "data_quality_guardrail"
        confidence_source = (
            "data_quality_guardrail"
            if isinstance(data_quality_report, dict) and data_quality_report.get("confidenceCap") not in (None, 100)
            else "llm" if model_used else "fallback"
        )

        data_sources: List[Dict[str, Any]] = []
        for name, field in runtime_data.items():
            if not isinstance(field, dict):
                continue
            data_sources.append({
                "name": name,
                "status": self._runtime_data_status(field),
                "provider": self._safe_public_text(field.get("source")),
                "updated_at": None,
                "notes": self._safe_public_text(field.get("final_reason")),
            })
        for name, block_name in (
            ("technical", "technicals"),
            ("fundamental", "fundamentals"),
            ("sentiment", "sentiment_analysis"),
            ("quote", "realtime_context"),
        ):
            if any(source.get("name") == name for source in data_sources):
                continue
            block = structured.get(block_name) if isinstance(structured.get(block_name), dict) else {}
            if block:
                data_sources.append({
                    "name": name,
                    "status": self._status_from_structured(block),
                    "provider": self._safe_public_text(block.get("source")),
                    "updated_at": None,
                    "notes": None,
                })

        signals = []
        for item in decision_context.get("score_breakdown") or []:
            if not isinstance(item, dict):
                continue
            signals.append({
                "name": self._safe_public_text(item.get("label")) or "signal",
                "value": item.get("score"),
                "impact": str(item.get("tone") or "neutral"),
                "source": "technical_rule" if "技术" in str(item.get("label") or "") else "rule",
                "weight": None,
            })

        action_value = self._normalize_action(
            getattr(result, "decision_type", None) or getattr(result, "operation_advice", None)
        )
        confidence_value = self._confidence_numeric(getattr(result, "confidence_level", None))
        entry_value = _first_present(sniper_points.get("ideal_buy"), sniper_points.get("secondary_buy"))
        target_value = sniper_points.get("take_profit")
        stop_value = sniper_points.get("stop_loss")

        def _level_source(value: Any) -> str:
            if not value:
                return "unknown"
            if key_levels_ungrounded or _is_ungrounded_level(value):
                return "data_quality_guardrail"
            return "llm"

        trace = {
            "engine_version": "analysis_decision_trace_v1",
            "mode": mode,
            "endpoint": "/api/v1/analysis/analyze",
            "task_id": query_id,
            "symbol": getattr(result, "code", None),
            "market": self._market_from_symbol(getattr(result, "code", "")),
            "generated_at": to_beijing_iso8601(datetime.utcnow()),
            "decision_fields": {
                "action": {
                    "value": action_value,
                    "source": action_source,
                    "confidence": confidence_value,
                    "notes": "Final scalar action may be stabilized after LLM JSON parsing." if has_rule_scoring else None,
                },
                "score": {
                    "value": getattr(result, "sentiment_score", None),
                    "source": score_source,
                    "scale": "0-100",
                    "notes": (
                        data_quality_report.get("scoreSuppressedReason")
                        if score_suppressed and isinstance(data_quality_report, dict)
                        else (
                            "Composite score uses deterministic market/technical/fundamental/news weights."
                            if has_rule_scoring
                            else None
                        )
                    ),
                },
                "confidence": {
                    "value": getattr(result, "confidence_level", None),
                    "source": confidence_source,
                    "notes": (
                        f"Confidence capped by data quality at {data_quality_report.get('confidenceCap')}."
                        if (
                            isinstance(data_quality_report, dict)
                            and data_quality_report.get("confidenceCap") not in (None, 100)
                        )
                        else "Confidence is read from the LLM dashboard scalar when available."
                    ),
                },
                "entry": {
                    "value": entry_value,
                    "source": _level_source(entry_value),
                },
                "target": {
                    "value": target_value,
                    "source": _level_source(target_value),
                },
                "stop": {
                    "value": stop_value,
                    "source": _level_source(stop_value),
                },
            },
            "data_sources": data_sources,
            "signals": signals[:8],
            "llm": {
                "used": bool(model_used),
                "provider": provider or "unknown",
                "model": model_used or None,
                "template": "decision_dashboard_v2" if model_used else None,
                "structured_output": bool(getattr(result, "llm_structured_output", bool(model_used))),
                "schema_validated": bool(getattr(result, "llm_schema_validated", False)),
                "prompt_exposed": False,
            },
            "conflicts": [],
            "limitations": [],
        }
        trace["limitations"] = self._build_decision_trace_limitations(structured, data_sources)
        trace["conflicts"] = self._detect_decision_trace_conflicts(
            trace=trace,
            result=result,
            dashboard=dashboard,
            position_strategy=position_strategy,
            structured=structured,
        )
        return trace

    def _build_decision_trace_limitations(
        self,
        structured: Dict[str, Any],
        data_sources: List[Dict[str, Any]],
    ) -> List[str]:
        limitations: List[str] = []
        quality = structured.get("data_quality") if isinstance(structured.get("data_quality"), dict) else {}
        for item in quality.get("missing_fields") or []:
            text = self._safe_public_text(item)
            if text:
                limitations.append(f"{text} missing")
        for source in data_sources:
            if source.get("status") in {"missing", "stale", "fallback"}:
                limitations.append(f"{source.get('name')} data {source.get('status')}")
        return list(dict.fromkeys(limitations))[:8]

    def _detect_decision_trace_conflicts(
        self,
        *,
        trace: Dict[str, Any],
        result: Any,
        dashboard: Dict[str, Any],
        position_strategy: Dict[str, Any],
        structured: Dict[str, Any],
    ) -> List[Dict[str, str]]:
        conflicts: List[Dict[str, str]] = []
        action = str((trace.get("decision_fields") or {}).get("action", {}).get("value") or "").lower()
        plan_text = " ".join(
            str(value or "")
            for value in [
                position_strategy.get("entry_plan"),
                position_strategy.get("suggested_position"),
                position_strategy.get("risk_control"),
                getattr(result, "analysis_summary", None),
            ]
        ).lower()
        buy_terms = ("buy", "add", "accumulate", "entry", "建仓", "买入", "加仓", "分批")
        sell_terms = ("sell", "reduce", "avoid", "卖", "减", "规避")
        if any(term in action for term in sell_terms) and any(term in plan_text for term in buy_terms):
            conflicts.append({
                "type": "action_plan_mismatch",
                "severity": "warning",
                "message": "Action says sell/reduce/avoid but the execution plan includes buy/add/accumulate wording. Treat no-position and held-position advice separately.",
            })
        risk_text = " ".join(str(value or "") for value in [
            getattr(result, "risk_warning", None),
            position_strategy.get("risk_control"),
        ]).lower()
        if "buy" in action and any(term in risk_text for term in ("trend invalid", "severe data missing", "趋势失效", "严重缺失")):
            conflicts.append({
                "type": "buy_with_invalidating_risk",
                "severity": "warning",
                "message": "Action says buy but risk text references trend invalidation or severe data gaps.",
            })
        quality = structured.get("data_quality") if isinstance(structured.get("data_quality"), dict) else {}
        missing_fields = quality.get("missing_fields") if isinstance(quality.get("missing_fields"), list) else []
        confidence_numeric = (trace.get("decision_fields") or {}).get("confidence", {}).get("value")
        high_confidence = self._confidence_numeric(confidence_numeric) or 0
        if len(missing_fields) >= 3 and high_confidence >= 0.7:
            conflicts.append({
                "type": "low_data_quality_high_confidence",
                "severity": "warning",
                "message": "Data quality is low or sparse while final confidence is high.",
            })
        fundamental_block = structured.get("fundamentals") if isinstance(structured.get("fundamentals"), dict) else {}
        fundamental_text = " ".join(str(value or "") for value in [
            getattr(result, "fundamental_analysis", None),
            (dashboard.get("intelligence") or {}).get("earnings_outlook") if isinstance(dashboard.get("intelligence"), dict) else None,
        ]).lower()
        strong_terms = ("strong", "excellent", "robust", "确定", "强劲", "优秀", "显著")
        fundamental_missing = [
            item for item in missing_fields
            if "fundamental" in str(item).lower() or "fundamentals" in str(item).lower()
        ]
        if (len(fundamental_missing) >= 2 or self._status_from_structured(fundamental_block) == "missing") and any(term in fundamental_text for term in strong_terms):
            conflicts.append({
                "type": "fundamental_claim_with_missing_data",
                "severity": "warning",
                "message": "Fundamental data is sparse but the report uses strong fundamental judgement.",
            })
        return conflicts

    def _build_analysis_response(
        self,
        result: Any,
        query_id: str,
        report_type: str = "detailed",
    ) -> Dict[str, Any]:
        """
        构建分析响应
        
        Args:
            result: AnalysisResult 对象
            query_id: 查询 ID
            report_type: 归一化后的报告类型
            
        Returns:
            格式化的响应字典
        """
        report_language = normalize_report_language(getattr(result, "report_language", "zh"))
        stock_name = get_localized_stock_name(getattr(result, "name", None), result.code, report_language)
        resolved_query_id = str(getattr(result, "query_id", None) or query_id)
        report = self._build_report_payload(
            result,
            query_id=resolved_query_id,
            report_type=report_type,
        )
        runtime_execution = self._attach_report_delivery_runtime(
            getattr(result, "runtime_execution", None),
            report,
        )

        response = {
            "stock_code": result.code,
            "stock_name": stock_name,
            "query_id": resolved_query_id,
            "report": report,
            "runtime_execution": runtime_execution,
            "notification_result": getattr(result, "notification_result", None),
        }
        if isinstance(report.get("researchReadiness"), dict):
            response["researchReadiness"] = report["researchReadiness"]
        if isinstance(report.get("evidenceCoverageFrame"), dict):
            response["evidenceCoverageFrame"] = report["evidenceCoverageFrame"]
        if isinstance(report.get("singleStockEvidencePacket"), dict):
            response["singleStockEvidencePacket"] = report["singleStockEvidencePacket"]
        if isinstance(report.get("evidenceCitationFrame"), dict):
            response["evidenceCitationFrame"] = report["evidenceCitationFrame"]
        if isinstance(report.get("sourceProvenanceFrame"), list):
            response["sourceProvenanceFrame"] = report["sourceProvenanceFrame"]
        return response

    @staticmethod
    def _attach_report_delivery_runtime(
        runtime_execution: Optional[Dict[str, Any]],
        report: Dict[str, Any],
    ) -> Dict[str, Any]:
        runtime = dict(runtime_execution) if isinstance(runtime_execution, dict) else {}
        details = report.get("details") if isinstance(report.get("details"), dict) else {}
        standard_report = details.get("standard_report")
        has_standard_report = isinstance(standard_report, dict)

        runtime_report = runtime.get("report") if isinstance(runtime.get("report"), dict) else {}
        runtime["report"] = {
            **runtime_report,
            "standard_report": {
                "status": "ok" if has_standard_report else "failed",
                "present": has_standard_report,
                "truth": "actual",
                "path": "task.result.report.details.standard_report",
                "final_reason": None if has_standard_report else "standard_report 缺失，首页标准卡片无法消费结构化结果。",
            },
        }

        existing_steps = runtime.get("steps") if isinstance(runtime.get("steps"), list) else []
        next_steps = [
            step for step in existing_steps
            if not (isinstance(step, dict) and str(step.get("key") or "").strip() == "standard_report")
        ]
        next_steps.append({"key": "standard_report", "status": "ok" if has_standard_report else "failed"})
        runtime["steps"] = next_steps
        return runtime
